"""Repository-scale sweep with a *single* measurement protocol.

For every store size the script records, on the same machine and in one process
lifetime:

  build_s           store construction time (data generation + rdflib ingest)
  peak_mb           peak Python allocation during construction (tracemalloc)
  index_s           anchor/entity index build time
  gsr               mean graph scan ratio over 100 stratified queries
  hits1 / ac1       retrieval quality at that size
  mean/p95 latency  serial, one request at a time, cache cleared for LLM variants

The original submission's scaling table mixed a 30-query LLM run with a
93-query non-LLM run and reported the unpruned variant's scan-only time in a
column labelled "latency"; here every variant is measured the same way, and the
LLM variants are labelled "llm_serial" so they are never compared with
scan-only numbers.

Usage:
  python experiments/scaling_ict.py --sizes 10000 50000 100000 200000 \
      --llm-n 20 --fast-n 100 --out results/scaling
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import statistics
import os
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd

# Portable source lookup: RDF_LLM_EA_SRC env var overrides the bundled copy.
SRC = Path(os.environ.get(
    "RDF_LLM_EA_SRC",
    str(Path(__file__).resolve().parents[1] / "upstream")))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import score  # noqa: E402
from engine import CandidateAnchorMapper  # noqa: E402
from baselines_extra import RealSparqlBaseline  # noqa: E402
from run_audit_experiment import build_systems  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import SEED, build_dataset  # noqa: E402

LOG = logging.getLogger("scaling")
ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
               "B": ["http://example.org/schemaB/alias"]}


def stratified(queries, n, seed=11):
    import random
    cats = sorted({q.category for q in queries})
    per = max(1, n // len(cats))
    rng = random.Random(seed)
    out = []
    for c in cats:
        pool = [q for q in queries if q.category == c]
        out.extend(rng.sample(pool, min(per, len(pool))))
    return out


def measure(sys_, variant, subset, total, use_extra: bool = False):
    from run_audit_experiment import run_variant
    rows = []
    for q in subset:
        t0 = time.perf_counter()
        res = (sys_.run(q.text, {"category": q.category}) if use_extra
               else run_variant(sys_, variant, q, {"category": q.category}))
        wall = (time.perf_counter() - t0) * 1000.0
        r = {"wall_ms": round(wall, 3)}
        r.update(score(res, q.gt_uris, q.gt_values, total))
        rows.append(r)
    lat = [r["wall_ms"] for r in rows]
    return {
        "n": len(rows),
        "mean_ms": round(statistics.fmean(lat), 3),
        "p95_ms": round(float(np.percentile(lat, 95)), 3),
        "hits1": round(statistics.fmean([r["hits1"] for r in rows]), 4),
        "ac1": round(statistics.fmean([r["ac1"] for r in rows]), 4),
        "gsr": round(statistics.fmean([r["gsr"] for r in rows]), 8),
        "triples_scanned": round(statistics.fmean([r["triples_scanned"] for r in rows]), 1),
        "ctx_triples": round(statistics.fmean([r["ctx_triples"] for r in rows]), 2),
        "mean_traversal_ms": round(statistics.fmean([r["t_traversal_ms"] for r in rows]), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="+", type=int,
                    default=[10_000, 50_000, 100_000, 200_000])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--llm-n", type=int, default=20)
    ap.add_argument("--fast-n", type=int, default=100)
    ap.add_argument("--extra-systems", nargs="+", default=["sparql_real"])
    ap.add_argument("--out", default="results/scaling")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(out / "run.log", mode="w", encoding="utf-8")])

    recs = []
    for size in args.sizes:
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        bundle = build_dataset(size, seed=args.seed)
        build_s = time.perf_counter() - t0
        peak_mb = tracemalloc.get_traced_memory()[1] / 1e6
        tracemalloc.stop()
        total = bundle.total_triples
        n_q = 500
        bench = build_benchmark(bundle, n_1hop=n_q * 2 // 5, n_2hop=n_q * 3 // 10,
                               n_cross=n_q - n_q * 2 // 5 - n_q * 3 // 10,
                               seed=args.seed + 1)
        t1 = time.perf_counter()
        CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
        index_s = time.perf_counter() - t1

        sys_ = build_systems(bundle, use_llm="ollama", coverage=0.92,
                             num_predict=256, memory_seed=args.seed + 3)
        LOG.info("size=%d total=%d build=%.2fs peak=%.1fMB index=%.2fs",
                 size, total, build_s, peak_mb, index_s)

        base = dict(target=size, triples=total, build_s=round(build_s, 2),
                    peak_mb=round(peak_mb, 1), index_s=round(index_s, 2))

        for v in ("full_system", "no_aligner_k6", "no_predicate_constraint",
                  "no_pruning", "vector_graphrag", "sparql_baseline"):
            n = args.llm_n if v in ("full_system", "no_predicate_constraint",
                                    "no_pruning") else args.fast_n
            subset = stratified(bench.queries, n, seed=11 + size % 97)
            if v in ("full_system", "no_predicate_constraint", "no_pruning"):
                llm = getattr(sys_.engine, "llm", None)
                if llm is not None and hasattr(llm, "_cache"):
                    llm._cache.clear()
            r = measure(sys_, v, subset, total)
            r.update(base, variant=v,
                     protocol="llm_serial" if v in
                     ("full_system", "no_predicate_constraint", "no_pruning")
                     else "serial")
            recs.append(r)
            LOG.info("  %-24s n=%d mean=%.2fms gsr=%.3e hits1=%.3f",
                     v, r["n"], r["mean_ms"], r["gsr"], r["hits1"])

        # fairness-corrected SPARQL, same protocol, so the scaling claim does
        # not rest on the capability-limited legacy baseline
        if "sparql_real" in args.extra_systems:
            mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
            sp = RealSparqlBaseline(bundle.graphs, mapper, alias_preds=ALIAS_PREDS)
            subset = stratified(bench.queries, args.fast_n, seed=101 + size % 97)
            r = measure(sp, "sparql_real", subset, total, use_extra=True)
            r.update(base, variant="sparql_real", protocol="serial")
            recs.append(r)
            LOG.info("  %-24s n=%d mean=%.2fms gsr=%.3e hits1=%.3f",
                     "sparql_real", r["n"], r["mean_ms"], r["gsr"], r["hits1"])

        pd.DataFrame(recs).to_csv(out / "scaling.csv", index=False,
                                  encoding="utf-8-sig")
        (out / "run_config.json").write_text(json.dumps(
            dict(vars(args), timestamp=time.strftime("%Y-%m-%d %H:%M:%S")),
            ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.DataFrame(recs)
    # log-log fit of GSR against |T| per variant
    fits = []
    for v, g in df.groupby("variant"):
        g = g[g.gsr > 0]
        if len(g) < 3:
            continue
        x = np.log(g.triples.values.astype(float))
        y = np.log(g.gsr.values.astype(float))
        slope, intercept = np.polyfit(x, y, 1)
        yhat = slope * x + intercept
        ss_res = float(((y - yhat) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        fits.append({"variant": v, "gsr_exponent": round(float(slope), 4),
                     "r2": round(1 - ss_res / ss_tot, 6) if ss_tot else "",
                     "n_points": len(g),
                     "latency_growth": round(float(
                         g.mean_ms.iloc[-1] / g.mean_ms.iloc[0]), 3)})
    pd.DataFrame(fits).to_csv(out / "gsr_fit.csv", index=False,
                              encoding="utf-8-sig")
    print(df.to_string(index=False))
    print()
    print(pd.DataFrame(fits).to_string(index=False))


if __name__ == "__main__":
    main()
