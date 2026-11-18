"""Clean latency protocol for the revision (replaces the mixed protocol of the
original submission, where one table reported a cache-warm measurement and
another a 4-worker loaded measurement).

Two protocols, measured on the same stratified query subset:

  serial_service  one request at a time; the aligner's plan cache is cleared
                  before the pass, so every query pays its own model call.
                  This is *service time*, the quantity that matters for
                  capacity planning.
  concurrent_4    4 worker threads over the same subset, cache cleared again.
                  Reported as *loaded response time* plus wall-clock throughput.
                  The local Ollama backend serves one request at a time, so this
                  protocol measures queueing, not parallelism.

Warm-up requests are executed and discarded before timing.

Usage:
  python experiments/latency_ict.py --n 40 --out results/latency
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
from run_audit_experiment import build_systems  # noqa: E402
from baselines_extra import RealSparqlBaseline  # noqa: E402
from dense_baseline import DenseMultilingualBaseline  # noqa: E402
from translit_baseline import TranslitLinker  # noqa: E402
from engine import CandidateAnchorMapper  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import SEED, build_dataset  # noqa: E402

LOG = logging.getLogger("latency")

LLM_VARIANTS = ["full_system", "no_predicate_constraint", "no_pruning"]
FAST_VARIANTS = ["no_aligner_k6", "vector_graphrag", "sparql_baseline"]
ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
               "B": ["http://example.org/schemaB/alias"]}
DEFAULT_MODEL = os.environ.get("E5_MODEL_PATH", "intfloat/multilingual-e5-small")


def _clear_cache(sys_) -> bool:
    llm = getattr(getattr(sys_, "engine", None), "llm", None)
    if llm is not None and hasattr(llm, "_cache"):
        llm._cache.clear()
        return True
    return False


def stratified(queries, n: int, seed: int = 1234):
    import random
    cats = sorted({q.category for q in queries})
    per = max(1, n // len(cats))
    rng = random.Random(seed)
    out = []
    for c in cats:
        pool = [q for q in queries if q.category == c]
        out.extend(rng.sample(pool, min(per, len(pool))))
    return out


def one(sys_, variant, q, total_triples):
    """Time one query.

    ``sys_`` is either the legacy container (with ``.engine``) or one of the
    fairness-corrected baseline objects, which expose ``.run()`` directly.
    """
    t0 = time.perf_counter()
    if hasattr(sys_, "engine") and not hasattr(sys_, "run"):
        from run_audit_experiment import run_variant
        res = run_variant(sys_, variant, q, {"category": q.category})
    else:
        res = sys_.run(q.text, {"category": q.category})
    wall = (time.perf_counter() - t0) * 1000.0
    rec = {"qid": q.qid, "variant": variant, "category": q.category,
           "wall_ms": round(wall, 3)}
    rec.update(score(res, q.gt_uris, q.gt_values, total_triples))
    return rec


def summarize(rows: list[dict], variant: str, protocol: str, wall_s: float,
              workers: int, warmup: int) -> dict:
    lat = [r["wall_ms"] for r in rows]
    return {
        "variant": variant, "protocol": protocol, "workers": workers,
        "warmup": warmup, "n": len(rows),
        "mean_ms": round(statistics.fmean(lat), 3),
        "median_ms": round(statistics.median(lat), 3),
        "p95_ms": round(float(np.percentile(lat, 95)), 3),
        "sd_ms": round(statistics.stdev(lat), 3) if len(lat) > 1 else 0.0,
        "wall_s": round(wall_s, 3),
        "qps": round(len(rows) / wall_s, 4) if wall_s > 0 else "",
        "mean_llm_ms": round(statistics.fmean([r["t_llm_ms"] for r in rows]), 3),
        "mean_surface_ms": round(statistics.fmean([r["t_surface_ms"] for r in rows]), 4),
        "mean_traversal_ms": round(statistics.fmean([r["t_traversal_ms"] for r in rows]), 4),
        "hits1": round(statistics.fmean([r["hits1"] for r in rows]), 4),
        "ac1": round(statistics.fmean([r["ac1"] for r in rows]), 4),
        "gsr": round(statistics.fmean([r["gsr"] for r in rows]), 8),
        "ctx_triples": round(statistics.fmean([r["ctx_triples"] for r in rows]), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", type=int, default=50_000)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=40, help="queries per timed pass")
    ap.add_argument("--warmup", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--coverage", type=float, default=0.92)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default="results/latency")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(out / "run.log", mode="w", encoding="utf-8")])

    bundle = build_dataset(args.triples, seed=args.seed)
    n_1 = args.queries * 2 // 5
    n_2 = args.queries * 3 // 10
    bench = build_benchmark(bundle, n_1hop=n_1, n_2hop=n_2,
                            n_cross=args.queries - n_1 - n_2, seed=args.seed + 1)
    sys_ = build_systems(bundle, use_llm="ollama", coverage=args.coverage,
                         num_predict=256, memory_seed=args.seed + 3)
    total = bundle.total_triples
    subset = stratified(bench.queries, args.n)
    LOG.info("store=%d | timed subset=%d %s", total, len(subset),
             dict(pd.Series([q.category for q in subset]).value_counts()))

    rows, summary = [], []

    # ---- protocol 1: serial service time (cache cleared) ----------------
    for v in LLM_VARIANTS:
        cleared = _clear_cache(sys_)
        LOG.info("[serial] %s (cache cleared=%s, warm-up=%d)", v, cleared, args.warmup)
        for q in subset[:args.warmup]:
            one(sys_, v, q, total)
        t0 = time.perf_counter()
        got = [one(sys_, v, q, total) for q in subset]
        wall = time.perf_counter() - t0
        rows.extend(got)
        summary.append(summarize(got, v, "serial_service", wall, 1, args.warmup))
        LOG.info("[serial] %s mean=%.1fms qps=%.2f", v,
                 summary[-1]["mean_ms"], summary[-1]["qps"])

    # ---- protocol 2: concurrent loaded response time --------------------
    for v in ["full_system"]:
        _clear_cache(sys_)
        for q in subset[:args.warmup]:
            one(sys_, v, q, total)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            got = list(pool.map(lambda q: one(sys_, v, q, total), subset))
        wall = time.perf_counter() - t0
        rows.extend(got)
        summary.append(summarize(got, v, "concurrent", wall, args.workers, args.warmup))
        LOG.info("[conc]   %s mean=%.1fms qps=%.3f", v,
                 summary[-1]["mean_ms"], summary[-1]["qps"])

    # ---- non-LLM systems: serial, larger subset -------------------------
    fast_subset = stratified(bench.queries, 200, seed=7)
    for v in FAST_VARIANTS:
        _clear_cache(sys_)
        for q in fast_subset[:args.warmup]:
            one(sys_, v, q, total)
        t0 = time.perf_counter()
        got = [one(sys_, v, q, total) for q in fast_subset]
        wall = time.perf_counter() - t0
        rows.extend(got)
        summary.append(summarize(got, v, "serial_service", wall, 1, args.warmup))
        LOG.info("[serial] %s mean=%.3fms qps=%.1f", v,
                 summary[-1]["mean_ms"], summary[-1]["qps"])

    # ---- fairness-corrected baselines: same serial protocol -------------
    # These replace the capability-limited legacy baselines for any claim
    # about what SPARQL or dense retrieval can do.
    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
    extra = {
        "sparql_real": RealSparqlBaseline(bundle.graphs, mapper,
                                          alias_preds=ALIAS_PREDS),
        "translit": TranslitLinker(bundle.graphs, mapper, ALIAS_PREDS),
        "dense": DenseMultilingualBaseline(bundle.graphs, mapper,
                                           model_name=args.model,
                                           top_k=5, expand_work=True),
    }
    for v, sysobj in extra.items():
        for q in fast_subset[:args.warmup]:
            one(sysobj, v, q, total)
        t0 = time.perf_counter()
        got = [one(sysobj, v, q, total) for q in fast_subset]
        wall = time.perf_counter() - t0
        rows.extend(got)
        summary.append(summarize(got, v, "serial_service", wall, 1, args.warmup))
        LOG.info("[serial] %s mean=%.3fms qps=%.1f", v,
                 summary[-1]["mean_ms"], summary[-1]["qps"])

    pd.DataFrame(rows).to_csv(out / "per_query.csv", index=False,
                              encoding="utf-8-sig")
    sm = pd.DataFrame(summary)
    sm.to_csv(out / "protocol_summary.csv", index=False, encoding="utf-8-sig")
    (out / "run_config.json").write_text(json.dumps(
        dict(vars(args), store_triples=total, n_subset=len(subset),
             timestamp=time.strftime("%Y-%m-%d %H:%M:%S")),
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(sm.to_string(index=False))


if __name__ == "__main__":
    main()
