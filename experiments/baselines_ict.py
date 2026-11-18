"""Run the fairness-corrected baselines on one or more benchmark seeds.

Two baselines are added to the revision, both on the identical store and query
set as the main run:

  sparql_real : genuine SPARQL 1.1 executed by rdflib's query engine, with a
                two-hop property path over work links and label/alias matching.
                (The legacy "SPARQL" baseline of the original submission never
                issued a SPARQL query at all; it walked Python triple patterns.)
  ml_vector   : multilingual dense retrieval (intfloat/multilingual-e5-small)
                over entity documents + graph expansion, i.e. the same
                "dense seed then traverse" design as the hashed-encoder
                baseline, but with a genuinely cross-lingual encoder.
  ml_vector_ne: the same dense retrieval without graph expansion, which
                isolates what the graph step contributes.

Usage:
  python experiments/baselines_ict.py --seed 20260101 --queries 500 \
      --out results/baselines/seed_20260101
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Portable source lookup: RDF_LLM_EA_SRC env var overrides the bundled copy.
SRC = Path(os.environ.get(
    "RDF_LLM_EA_SRC",
    str(Path(__file__).resolve().parents[1] / "upstream")))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import score  # noqa: E402
from baselines_extra import RealSparqlBaseline  # noqa: E402
from dense_baseline import DenseMultilingualBaseline  # noqa: E402
from translit_baseline import TranslitLinker  # noqa: E402
from engine import CandidateAnchorMapper  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import build_dataset  # noqa: E402

LOG = logging.getLogger("baselines_ict")

ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
               "B": ["http://example.org/schemaB/alias"]}

# Pin the encoder revision via E5_MODEL_PATH if a local snapshot is desired;
# the default is the public Hugging Face model name (auto-downloaded).
DEFAULT_MODEL = os.environ.get("E5_MODEL_PATH", "intfloat/multilingual-e5-small")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", type=int, default=50_000)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--out", required=True)
    ap.add_argument("--systems", default="sparql_real,dense,dense_ne,translit")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0,
                    help="debug: only the first N queries")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(out / "run.log", mode="w", encoding="utf-8")])

    t0 = time.perf_counter()
    bundle = build_dataset(args.triples, seed=args.seed)
    n_1 = args.queries * 2 // 5
    n_2 = args.queries * 3 // 10
    bench = build_benchmark(bundle, n_1hop=n_1, n_2hop=n_2,
                            n_cross=args.queries - n_1 - n_2, seed=args.seed + 1)
    queries = bench.queries[:args.limit] if args.limit else bench.queries
    LOG.info("store=%d triples / %d entities | %d queries | build %.1fs",
             bundle.total_triples, len(bundle.entities), len(queries),
             time.perf_counter() - t0)

    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
    systems = {}
    build_meta = {}
    wanted = [s for s in args.systems.split(",") if s]

    if "dense" in wanted or "dense_ne" in wanted:
        t1 = time.perf_counter()
        dn = DenseMultilingualBaseline(bundle.graphs, mapper,
                                       model_name=args.model, top_k=args.top_k,
                                       expand_work=True)
        build_meta.update(dense_model=args.model, dense_dim=int(dn.matrix.shape[1]),
                          dense_docs=dn.n_docs,
                          dense_model_load_s=round(dn.model_load_s, 2),
                          dense_encode_s=round(dn.encode_s, 2),
                          dense_device=dn.device)
        systems["dense"] = dn
        if "dense_ne" in wanted:
            systems["dense_ne"] = DenseMultilingualBaseline(
                bundle.graphs, mapper, model_name=args.model,
                top_k=args.top_k, expand_work=False)
        LOG.info("dense baselines built in %.1fs (%d docs, dim=%d, device=%s)",
                 time.perf_counter() - t1, dn.n_docs, dn.matrix.shape[1], dn.device)

    if "sparql_real" in wanted:
        systems["sparql_real"] = RealSparqlBaseline(bundle.graphs, mapper,
                                                   alias_preds=ALIAS_PREDS)

    if "translit" in wanted:
        systems["translit"] = TranslitLinker(bundle.graphs, mapper,
                                             alias_preds=ALIAS_PREDS)

    rows = []
    for name, sysobj in systems.items():
        LOG.info("running %s on %d queries", name, len(queries))
        t1 = time.perf_counter()
        for i, q in enumerate(queries):
            tq = time.perf_counter()
            res = sysobj.run(q.text, {"category": q.category})
            wall = (time.perf_counter() - tq) * 1000.0
            rec = {"qid": q.qid, "system": name, "category": q.category,
                   "lang": q.lang, "intent": q.intent, "query": q.text,
                   "wall_ms": round(wall, 4)}
            rec.update(score(res, q.gt_uris, q.gt_values, bundle.total_triples))
            rows.append(rec)
            if (i + 1) % 100 == 0:
                LOG.info("  %s %d/%d (%.0fs)", name, i + 1, len(queries),
                         time.perf_counter() - t1)
        LOG.info("  %s done in %.1fs", name, time.perf_counter() - t1)

    df = pd.DataFrame(rows)
    df.to_csv(out / "per_query.csv", index=False, encoding="utf-8-sig")

    agg = (df.groupby("system")[["hits1", "mrr", "ac1", "vic", "gsr",
                                 "ctx_triples", "wall_ms"]]
             .mean().round(6).reset_index())
    agg["n"] = df.groupby("system").size().values
    agg.to_csv(out / "aggregate.csv", index=False, encoding="utf-8-sig")

    cat = (df.groupby(["system", "category"])[["hits1", "mrr", "ac1", "vic",
                                               "ctx_triples", "wall_ms"]]
             .mean().round(6).reset_index())
    cat["n"] = df.groupby(["system", "category"]).size().values
    cat.to_csv(out / "per_category.csv", index=False, encoding="utf-8-sig")

    if "sparql_real" in systems:
        rs = systems["sparql_real"]
        build_meta.update(sparql_calls=rs.n_sparql_calls,
                          sparql_2hop_queries=rs.n_2hop_queries,
                          sparql_resolve_hits=rs.n_resolve_hits)

    cfg = dict(vars(args), store_triples=bundle.total_triples,
               entities=len(bundle.entities), n_queries=len(queries),
               systems=wanted, **build_meta,
               timestamp=time.strftime("%Y-%m-%d %H:%M:%S"))
    (out / "run_config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(agg.to_string(index=False))
    print()
    print(cat.to_string(index=False))


if __name__ == "__main__":
    main()
