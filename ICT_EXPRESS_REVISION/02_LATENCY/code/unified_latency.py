"""P0 Stage 3: unified latency workload for all executable systems.

All systems run the SAME 24 qids (8 per category), SAME order, SAME warm-up,
SAME cache policy, and TWO timed repeats. Serial service time only; no
queueing is included. Dense e5 is excluded because torch/transformers are not
installed in this environment; it is documented as an environment limitation.

Outputs:
  results/LATENCY_RAW_RUNS.csv
  results/LATENCY_PER_QUERY.csv
  results/LATENCY_SUMMARY.csv
  results/LATENCY_EXPERIMENT_CONFIG.yaml
"""
from __future__ import annotations

import json
import logging
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
SUB = ROOT / "ict_express_submission"
REV = ROOT / "ICT_EXPRESS_REVISION" / "02_LATENCY"
sys.path.insert(0, str(SUB / "upstream"))
sys.path.insert(0, str(SUB / "experiments"))

from metrics import score  # noqa: E402
from run_audit_experiment import build_systems, run_variant  # noqa: E402
from baselines_extra import RealSparqlBaseline  # noqa: E402
from translit_baseline import TranslitLinker  # noqa: E402
from engine import CandidateAnchorMapper  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import SEED, build_dataset  # noqa: E402

OUT = REV / "results"
LOGDIR = REV / "logs"
ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
               "B": ["http://example.org/schemaB/alias"]}
WARMUP = 2
REPEATS = 2
VARIANTS = ["full_system", "no_aligner_k6", "sparql_baseline",
            "vector_graphrag", "sparql_real", "translit"]
SERIAL_QIDS = ["Q0499", "Q0276", "Q0065", "Q0002", "Q0046", "Q0369",
               "Q0022", "Q0423", "Q0081", "Q0092", "Q0300", "Q0215",
               "Q0025", "Q0034", "Q0296", "Q0406", "Q0402", "Q0112",
               "Q0079", "Q0134", "Q0093", "Q0008", "Q0438", "Q0427"]


def preflight_sparql() -> str:
    """Fail loudly if rdflib's optional SPARQL parser dependencies are absent.

    The first run of this protocol silently returned zero hits for sparql_real
    because pyparsing was missing and RealSparqlBaseline caught the resulting
    exception.  Such an environment failure must not be reported as a result.
    """
    from importlib.metadata import PackageNotFoundError, version
    from rdflib import Graph

    try:
        g = Graph()
        list(g.query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        raise RuntimeError("rdflib SPARQL engine unavailable") from exc
    try:
        pyparsing_version = version("pyparsing")
    except PackageNotFoundError:  # pragma: no cover - environment guard
        pyparsing_version = "unknown"
    return f"rdflib SPARQL 1.1 engine; pyparsing={pyparsing_version}"


def clear_cache(sys_) -> bool:
    llm = getattr(getattr(sys_, "engine", None), "llm", None)
    if llm is not None and hasattr(llm, "_cache"):
        llm._cache.clear()
        return True
    return False


def timed(system, variant: str, q, total: int, rep: int) -> dict:
    t0 = time.perf_counter()
    if variant in {"sparql_real", "translit"}:
        res = system.run(q.text, {"category": q.category})
    else:
        res = run_variant(system, variant, q, {"category": q.category})
    wall = (time.perf_counter() - t0) * 1000.0
    rec = {
        "qid": q.qid, "category": q.category, "variant": variant,
        "repeat": rep, "protocol": "serial_service", "workers": 1,
        "wall_ms": round(wall, 3),
    }
    rec.update(score(res, q.gt_uris, q.gt_values, total))
    return rec


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(LOGDIR / "latency_run.log", mode="w", encoding="utf-8")])
    log = logging.getLogger("unified_latency")
    sparql_engine = preflight_sparql()
    log.info("SPARQL preflight passed: %s", sparql_engine)

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    bundle = build_dataset(50_000, seed=SEED)
    bench = build_benchmark(bundle)
    by_qid = {q.qid: q for q in bench.queries}
    queries = [by_qid[q] for q in SERIAL_QIDS]
    assert len(queries) == 24
    log.info("Unified workload: %d qids, categories=%s", len(queries),
             pd.Series([q.category for q in queries]).value_counts().to_dict())

    sys_ = build_systems(bundle, use_llm="ollama", coverage=0.92,
                         num_predict=256, memory_seed=SEED + 3)
    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
    extras = {
        "sparql_real": RealSparqlBaseline(bundle.graphs, mapper, alias_preds=ALIAS_PREDS),
        "translit": TranslitLinker(bundle.graphs, mapper, ALIAS_PREDS),
    }
    total = bundle.total_triples

    raw = []
    for variant in VARIANTS:
        system = extras.get(variant, sys_)
        cleared = clear_cache(sys_)
        log.info("Warm-up %s (cache cleared=%s)", variant, cleared)
        for q in queries[:WARMUP]:
            timed(system, variant, q, total, 0)
        for rep in range(1, REPEATS + 1):
            clear_cache(sys_)
            t0 = time.perf_counter()
            got = [timed(system, variant, q, total, rep) for q in queries]
            wall_s = time.perf_counter() - t0
            raw.extend(got)
            lat = [r["wall_ms"] for r in got]
            log.info("%s rep=%d mean=%.1fms median=%.1fms qps=%.2f",
                     variant, rep, statistics.fmean(lat), statistics.median(lat),
                     len(got) / wall_s)

    raw_df = pd.DataFrame(raw)
    raw_path = OUT / "LATENCY_RAW_RUNS.csv"
    raw_df.to_csv(raw_path, index=False)

    perq = raw_df.groupby(["variant", "qid", "category"], as_index=False).agg(
        mean_ms=("wall_ms", "mean"), median_ms=("wall_ms", "median"),
        min_ms=("wall_ms", "min"), max_ms=("wall_ms", "max"),
        ac1=("ac1", "mean"), vic=("vic", "mean"),
        mean_llm_ms=("t_llm_ms", "mean"),
        mean_traversal_ms=("t_traversal_ms", "mean"),
        n_runs=("wall_ms", "size"))
    perq_path = OUT / "LATENCY_PER_QUERY.csv"
    perq.to_csv(perq_path, index=False)

    summary = []
    for variant, g in raw_df.groupby("variant"):
        x = g.wall_ms.to_numpy()
        summary.append({
            "variant": variant, "protocol": "serial_service", "workers": 1,
            "n_qids": g.qid.nunique(), "n_runs": len(g), "repeats": REPEATS,
            "warmup": WARMUP,
            "mean_ms": round(float(x.mean()), 3),
            "median_ms": round(float(np.median(x)), 3),
            "sd_ms": round(float(x.std(ddof=1)), 3),
            "p95_ms": round(float(np.percentile(x, 95)), 3),
            "min_ms": round(float(x.min()), 3),
            "max_ms": round(float(x.max()), 3),
            "mean_llm_ms": round(float(g.t_llm_ms.mean()), 3),
            "mean_traversal_ms": round(float(g.t_traversal_ms.mean()), 4),
            "ac1": round(float(g.ac1.mean()), 4),
        })
    summary_path = OUT / "LATENCY_SUMMARY.csv"
    pd.DataFrame(summary).to_csv(summary_path, index=False)

    config = f"""protocol: serial_service
workload_qids: {json.dumps(SERIAL_QIDS)}
qids_per_category: 8
repeat_count: {REPEATS}
warmup_queries: {WARMUP}
workers: 1
cache_policy: llm_plan_cache_cleared_before_each_repeat
query_order: fixed (SERIAL_QIDS)
timeout_ms: 120000
queueing_included: false
model: qwen2.5:7b (Ollama, temperature 0, num_predict 256)
sparql_engine: {sparql_engine}
dense_e5_included: false
dense_e5_reason: torch/transformers not installed in this execution environment
started: {started}
finished: {time.strftime("%Y-%m-%d %H:%M:%S")}
"""
    config_path = OUT / "LATENCY_EXPERIMENT_CONFIG.yaml"
    config_path.write_text(config, encoding="utf-8")

    print(f"wrote {raw_path} rows={len(raw_df)}")
    print(f"wrote {perq_path} rows={len(perq)}")
    print(f"wrote {summary_path}")
    print(f"wrote {config_path}")
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
