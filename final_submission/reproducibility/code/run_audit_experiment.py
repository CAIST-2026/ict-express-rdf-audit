"""Audit-corrected experiment driver (Phase 2).

Why a separate driver instead of editing ``run_comprehensive_experiment.py``:
the original driver reproduces exactly the numbers printed in the manuscript,
and that reproduction has to stay possible. This driver is the *corrected*
protocol; the original stays as the reference implementation of the published
run.

Corrections implemented here
----------------------------
P0-1  num_predict is now 256 (was 90) -> removes the 11% JSON-truncation
      fallback to the mock planner (engine.py).
P0-3  ``--coverage`` exposes LLM_COVERAGE (was hard-coded 0.92, undisclosed).
P1    three explicitly separated protocols: serial service time, concurrent
      loaded response time, and system throughput (n / wall). Every protocol
      reports n, successes, failures, mean, median, P95 and total wall time.
      Warm-up calls are executed and discarded before timing.
P2    ``success_loose`` (legacy substring rule) is kept for continuity and is
      reported next to ``success_strict`` (correct entity ranked first AND the
      matched value present in the retrieved context). Faithfulness /
      relevance are computed by the deterministic proxy for every query AND by
      an independent local LLM judge on a stratified sample.
P3    adds ``no_predicate_constraint`` (removes only the predicate constraint)
      and ``no_aligner_k6`` (removes only alignment; candidate budget fixed at
      the full system's value) so that ablations change one factor.

Nothing is filled in for an experiment that has not run: every artefact is
written from measured values only.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from engine import (CandidateAnchorMapper, OllamaLLMFilter, MockLLMFilter,
                    NoisyAlignFilter, OptimizedExecutor, RetrievalEngine,
                    SparqlBaseline, VectorGraphRAGBaseline,
                    infer_predicate_constraints, local_name, schema_summary)
from judge import MockJudge, get_answerer, get_judge
from scalable_benchmark import build_benchmark
from scalable_data import SEED, build_dataset, build_llm_memory

LOG = logging.getLogger("audit_experiment")

VARIANTS = ["full_system", "no_aligner", "no_aligner_k6",
            "no_predicate_constraint", "no_pruning",
            "vector_graphrag", "sparql_baseline"]

# Variants whose per-query cost includes a real LLM call.
LLM_VARIANTS = {"full_system", "no_predicate_constraint"}


def _now_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _rank_of(gt_uris, ranked: list[str]) -> int:
    for i, uri in enumerate(ranked):
        if uri in gt_uris:
            return i
    return -1


def _claims(answer: str) -> list[str]:
    return [c.strip() for c in (answer or "").split(";") if c.strip()]


# ---------------------------------------------------------------------------
# System assembly
# ---------------------------------------------------------------------------
@dataclass
class Systems:
    graphs: dict
    engine: RetrievalEngine
    sparql: SparqlBaseline
    vector: VectorGraphRAGBaseline
    total_triples: int
    memory_coverage: float
    entities_memorised: int


def build_systems(bundle, exclude_uris=(), use_llm: str = "ollama",
                  coverage: float = 0.92, noise_seed: int = 7,
                  num_predict: int = 256, fail_prob: dict | None = None,
                  memory_seed: int = SEED,
                  align_error: float | None = None) -> Systems:
    graphs = bundle.graphs
    alias_preds = {"A": ["http://example.org/schemaA/别名"],
                   "B": ["http://example.org/schemaB/alias"]}
    mapper = CandidateAnchorMapper(graphs, alias_preds)
    knowledge, label_to_key, alias_index, uri_graph = build_llm_memory(
        bundle, coverage=coverage, seed=memory_seed)

    if use_llm == "ollama":
        aligner = OllamaLLMFilter(entity_vocab=mapper.index, knowledge=knowledge,
                                  label_to_key=label_to_key,
                                  alias_index=alias_index,
                                  num_predict=num_predict)
    elif use_llm == "openai" and os.environ.get("OPENAI_API_KEY"):
        from engine import OpenAILLMFilter
        aligner = OpenAILLMFilter(entity_vocab=mapper.index)
    else:
        base = MockLLMFilter(mapper.index, knowledge, label_to_key, alias_index)
        distractors = [u for e in bundle.entities for u in e.all_uris()
                       if u not in set(exclude_uris)]
        aligner = NoisyAlignFilter(base, uri_graph, fail_prob or {},
                                   seed=noise_seed, distractor_uris=distractors)

    # P6: robustness axis -- inject the *same* auditable alignment error process
    # on top of the real LLM aligner. In the published run this wrapper was only
    # attached to the mock path, so the LLM arm was never stress-tested.
    if align_error:
        distractors = [u for e in bundle.entities for u in e.all_uris()
                       if u not in set(exclude_uris)]
        aligner = NoisyAlignFilter(
            aligner, uri_graph,
            {"1-hop": align_error, "2-hop": align_error,
             "cross-lingual": align_error},
            seed=noise_seed, distractor_uris=distractors)
        LOG.info("Alignment-error injection ON: p=%.2f on every category",
                 align_error)

    return Systems(
        graphs=graphs,
        engine=RetrievalEngine(graphs, mapper, aligner),
        sparql=SparqlBaseline(graphs, mapper),
        vector=VectorGraphRAGBaseline(graphs, mapper, top_k=5),
        total_triples=sum(len(g) for g in graphs.values()),
        memory_coverage=coverage,
        entities_memorised=len(knowledge),
    )


ATTR_LOCAL_NAMES: set[str] = set()
def _init_attr_names() -> None:
    """Local names of answer-bearing attribute predicates (P6 stressor).

    Work links and labels are deliberately excluded: removing a link would
    destroy the 2-hop *structure* rather than remove evidence, which is a
    different failure mode and would confound the sweep.
    """
    from scalable_data import PRED
    for family, names in PRED.items():
        if family in ("link", "alias"):
            continue
        ATTR_LOCAL_NAMES.update(names)
_init_attr_names()


def drop_evidence(graphs: dict, frac: float, seed: int) -> int:
    """Delete a seeded random fraction of attribute triples from every graph.

    This is the P6 ``missing evidence`` stressor: the question is still asked,
    the gold answer is still defined by the generation record, but the triple
    that carries it may no longer be in the store.
    """
    if frac <= 0:
        return 0
    rng = random.Random(seed)
    removed = 0
    for g in graphs.values():
        victims = [t for t in g if local_name(str(t[1])) in ATTR_LOCAL_NAMES]
        k = int(round(len(victims) * frac))
        for t in rng.sample(victims, k):
            g.remove(t)
            removed += 1
    return removed


def run_variant(sys_: Systems, variant: str, q, meta: dict):
    # Baselines injected by run_baselines.py (optional dependencies).
    extras = getattr(sys_, "extras", None) or {}
    if variant in extras:
        return extras[variant].run(q.text, meta)
    if variant == "full_system":
        return sys_.engine.full_system(q.text, meta)
    if variant == "no_aligner":                 # legacy: also changes top_k
        return sys_.engine.no_aligner(q.text, meta, top_k=20)
    if variant == "no_aligner_k6":              # P3: single factor
        return sys_.engine.no_aligner(q.text, meta, top_k=6)
    if variant == "no_predicate_constraint":    # P3: single factor
        return sys_.engine.no_predicate_constraint(q.text, meta)
    if variant == "no_pruning":
        return sys_.engine.no_pruning(q.text, meta)
    if variant == "vector_graphrag":
        return sys_.vector.run(q.text, meta)
    if variant == "sparql_baseline":
        return sys_.sparql.run(q.text)
    raise ValueError(variant)


# ---------------------------------------------------------------------------
# Per-query scoring
# ---------------------------------------------------------------------------
def score_query(sys_: Systems, variant: str, q, answerer, judge_proxy,
                judge_llm, llm_judge_qids: set) -> dict:
    t0 = time.perf_counter()
    res = run_variant(sys_, variant, q, {"category": q.category})
    wall_ms = _now_ms(t0)

    q_constraints = infer_predicate_constraints(q.text)
    answer = answerer.answer(q.text, res.triples, q_constraints)
    faith_p, rel_p = judge_proxy.score(q.text, answer, res.triples, q.gt_values)

    rank = _rank_of(q.gt_uris, res.ranked_uris)
    gt = [str(v) for v in q.gt_values]
    # legacy (substring) rule - kept so the change is measurable
    success_loose = any(v in answer for v in gt)
    # strict rule: correct entity ranked first AND the matched value is
    # actually present in the retrieved context (evidence-grounded)
    ctx_objs = {str(o) for _s, _p, o in res.triples}
    matched = [v for v in gt if v in answer]
    grounded = any(v in ctx_objs for v in matched)
    success_strict = bool(rank == 0 and matched and grounded)

    faith_l = rel_l = ""
    if judge_llm is not None and q.qid in llm_judge_qids:
        try:
            f, r = judge_llm.score(q.text, answer, res.triples, q.gt_values)
            faith_l, rel_l = f, r
        except Exception as exc:                      # pragma: no cover
            LOG.warning("LLM judge failed on %s: %s", q.qid, exc)

    plan = getattr(res, "plan", None)
    return {
        "qid": q.qid, "variant": variant, "category": q.category,
        "lang": q.lang, "intent": q.intent,
        "hits1": 1.0 if rank == 0 else 0.0,
        "mrr": 0.0 if rank < 0 else 1.0 / (rank + 1),
        "success_loose": 1.0 if success_loose else 0.0,
        "success_strict": 1.0 if success_strict else 0.0,
        "faithfulness_proxy": faith_p,
        "relevance_proxy": rel_p,
        "faithfulness_llm": faith_l,
        "relevance_llm": rel_l,
        "n_claims": len(_claims(answer)),
        "evidence_grounded": 1.0 if grounded else 0.0,
        "gsr": res.scanned / max(1, sys_.total_triples),
        "triples_scanned": res.scanned,
        "label_index_scanned": res.label_scans,
        "context_triples": len(res.triples),
        "t_surface_ms": round(res.t_surface_ms, 4),
        "t_llm_ms": round(res.t_llm_ms, 4),
        "t_traversal_ms": round(res.t_traversal_ms, 4),
        "t_total_ms": round(wall_ms, 4),
        "failure_mode": getattr(res, "failure_mode", "ok"),
        "backend": getattr(plan, "backend", "-") if plan is not None else "-",
        "query": q.text, "answer": answer,
        "gt_values": "|".join(gt),
        "aligned_uris": "|".join(str(u) for u in res.ranked_uris[:4] if u),
    }


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------
def _proto_stats(lat_ms: list[float], wall_s: float, n_ok: int,
                 n_fail: int) -> dict:
    return {
        "n": len(lat_ms), "n_ok": n_ok, "n_fail": n_fail,
        "failure_rate": round(n_fail / max(1, n_ok + n_fail), 6),
        "mean_ms": round(statistics.fmean(lat_ms), 4) if lat_ms else "",
        "median_ms": round(statistics.median(lat_ms), 4) if lat_ms else "",
        "p95_ms": round(float(np.percentile(lat_ms, 95)), 4) if lat_ms else "",
        "wall_s": round(wall_s, 4),
        "qps": round(len(lat_ms) / wall_s, 6) if wall_s > 0 else "",
    }


def run_concurrent(sys_, queries, variants, workers: int, answerer,
                   judge_proxy, judge_llm, llm_judge_qids,
                   judge_variants: set | None = None,
                   clear_cache: bool = False) -> tuple[list, list]:
    """Protocol B: concurrent loaded response time + throughput.

    ``clear_cache=True`` empties the aligner's plan memo before each LLM-bound
    variant. Without it, a variant that runs after ``full_system`` pays no model
    call at all (every query has already been planned), which silently turns its
    end-to-end latency into a traversal-only number. For a throughput figure
    that reflects a stream of *distinct* queries, the cache must be cleared.
    """
    rows, proto = [], []
    judge_variants = judge_variants or set()
    for variant in variants:
        qids = llm_judge_qids if variant in judge_variants else set()
        if clear_cache and variant in LLM_VARIANTS:
            llm = getattr(getattr(sys_, "engine", None), "llm", None)
            if llm is not None and hasattr(llm, "_cache"):
                llm._cache.clear()
                LOG.info("[concurrent] cleared plan cache before %s", variant)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(score_query, sys_, variant, q, answerer,
                                judge_proxy, judge_llm, qids)
                    for q in queries]
            out = []
            done = 0
            step = max(1, len(futs) // 10)
            for f in as_completed(futs):
                out.append(f.result())
                done += 1
                if done % step == 0 or done == len(futs):
                    LOG.info("[concurrent] %-24s %d/%d done (%.0fs)",
                             variant, done, len(futs), time.perf_counter() - t0)
        wall = time.perf_counter() - t0
        rows.extend(out)
        lat = [r["t_total_ms"] for r in out]
        st = _proto_stats(lat, wall,
                          sum(1 for r in out if r["hits1"] == 1.0),
                          sum(1 for r in out if r["hits1"] == 0.0))
        st.update(variant=variant, protocol="concurrent", workers=workers,
                  warmup=0)
        proto.append(st)
        LOG.info("[concurrent] %-24s n=%d mean=%.3fms qps=%.3f",
                 variant, len(out), st["mean_ms"] or 0, st["qps"] or 0)
    return rows, proto


def run_serial(sys_, queries, variants, n_serial: int, warmup: int, answerer,
               judge_proxy) -> list:
    """Protocol A: serial service time (one request at a time, after warm-up)."""
    proto = []
    # stratified subset, same proportions as the full benchmark
    cats = sorted({q.category for q in queries})
    subset = []
    per = max(1, n_serial // len(cats))
    for c in cats:
        pool = [q for q in queries if q.category == c]
        rng = random.Random(1234)
        subset.extend(rng.sample(pool, min(per, len(pool))))
    for variant in variants:
        # AUDIT FIX: the aligner memoises plans (temperature=0), so a serial pass
        # that runs after the concurrent pass would measure cache hits instead of
        # service time. Clear it for the variants whose service time includes a
        # model call; the others (scan-only by construction) keep it, which is
        # exactly how they are reported.
        if variant in LLM_VARIANTS:
            llm = getattr(getattr(sys_, "engine", None), "llm", None)
            if llm is not None and hasattr(llm, "_cache"):
                llm._cache.clear()
                LOG.info("[serial]     cleared plan cache before %s", variant)
        warm_qs = subset[:warmup]
        for q in warm_qs:                    # warm-up: executed, not timed
            try:
                run_variant(sys_, variant, q, {"category": q.category})
            except Exception as exc:         # pragma: no cover
                LOG.warning("warm-up failed for %s/%s: %s", variant, q.qid, exc)
        lat, ok, fail = [], 0, 0
        t0 = time.perf_counter()
        for q in subset:
            r = score_query(sys_, variant, q, answerer, judge_proxy, None, set())
            lat.append(r["t_total_ms"])
            ok += int(r["hits1"] == 1.0)
            fail += int(r["hits1"] == 0.0)
        wall = time.perf_counter() - t0
        st = _proto_stats(lat, wall, ok, fail)
        st.update(variant=variant, protocol="serial", workers=1, warmup=warmup)
        proto.append(st)
        LOG.info("[serial]     %-24s n=%d mean=%.3fms qps=%.3f",
                 variant, len(lat), st["mean_ms"] or 0, st["qps"] or 0)
    return proto


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
AGG_METRICS = ["hits1", "mrr", "success_loose", "success_strict",
               "faithfulness_proxy", "relevance_proxy", "evidence_grounded",
               "gsr", "context_triples"]


def aggregate(rows: pd.DataFrame, variants) -> tuple[pd.DataFrame, pd.DataFrame]:
    agg_rows, cat_rows = [], []
    for v in variants:
        sub = rows[rows.variant == v]
        if sub.empty:
            continue
        rec = {"variant": v, "n": len(sub)}
        for m in AGG_METRICS:
            rec[m] = round(float(sub[m].mean()), 6)
        rec["backend_ollama"] = int((sub.backend == "ollama").sum())
        rec["backend_mock_fallback"] = int((sub.backend == "ollama->mock").sum())
        rec["fallback_rate"] = round(rec["backend_mock_fallback"] / len(sub), 4)
        agg_rows.append(rec)
        for cat, cs in sub.groupby("category"):
            cat_rows.append({
                "variant": v, "category": cat, "n": len(cs),
                "hits1": round(float(cs.hits1.mean()), 4),
                "mrr": round(float(cs.mrr.mean()), 4),
                "success_loose": round(float(cs.success_loose.mean()), 4),
                "success_strict": round(float(cs.success_strict.mean()), 4),
                "fallback_rate": round(float((cs.backend == "ollama->mock").mean()), 4),
            })
    return pd.DataFrame(agg_rows), pd.DataFrame(cat_rows)


def env_report() -> dict:
    """Best-effort hardware / software record (never invents values)."""
    info = {"platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "python": sys.version.split()[0],
            "machine": platform.machine()}
    try:
        info["cpu_count"] = os.cpu_count()
    except Exception:
        info["cpu_count"] = ""
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                             capture_output=True, text=True, timeout=5)
        info["memory_bytes"] = int(out.stdout.strip()) if out.stdout.strip() else ""
    except Exception:
        info["memory_bytes"] = ""
    for mod in ("numpy", "pandas", "rdflib", "matplotlib", "requests", "torch"):
        try:
            m = __import__(mod)
            info[f"ver_{mod}"] = getattr(m, "__version__", "")
        except Exception:
            info[f"ver_{mod}"] = "missing"
    try:
        import requests
        r = requests.get("http://localhost:11434/api/version", timeout=5)
        info["ollama_version"] = r.text.strip() if r.ok else f"http={r.status_code}"
    except Exception as exc:
        info["ollama_version"] = f"unavailable ({type(exc).__name__})"
    info["ollama_model"] = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    info["openai_key_present"] = bool(os.environ.get("OPENAI_API_KEY"))
    return info


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", type=int, default=50_000)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--seed", type=int, default=SEED,
                    help="store seed; benchmark uses seed+1, noise uses seed+2")
    ap.add_argument("--coverage", type=float, default=0.92,
                    help="fraction of entities present in the aligner's "
                         "cross-lingual profile (was hard-coded and undisclosed)")
    ap.add_argument("--num-predict", type=int, default=256,
                    help="Ollama token budget for the JSON plan (was 90)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--serial-queries", type=int, default=100)
    ap.add_argument("--serial-warmup", type=int, default=10)
    ap.add_argument("--judge", choices=("none", "ollama", "mock"), default="ollama")
    ap.add_argument("--judge-queries", type=int, default=60)
    ap.add_argument("--judge-variants", default="full_system,vector_graphrag")
    ap.add_argument("--llm", choices=("ollama", "openai", "mock"), default="ollama")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--out", default="outputs_audit")
    ap.add_argument("--skip-scalability", action="store_true")
    ap.add_argument("--skip-serial", action="store_true")
    ap.add_argument("--clear-cache-concurrent", action="store_true",
                    help="clear the aligner plan cache before each LLM-bound "
                         "variant so throughput reflects distinct queries")
    ap.add_argument("--skip-concurrent", action="store_true",
                    help="run only the serial protocol (used to re-measure "
                         "service time after the plan-cache fix)")
    ap.add_argument("--align-error", type=float, default=None,
                    help="P6: inject this alignment failure probability on top "
                         "of the REAL LLM aligner (categories 1-hop/2-hop/"
                         "cross-lingual). Default None = published behaviour.")
    ap.add_argument("--missing-evidence", type=float, default=0.0,
                    help="P6: fraction of answer-bearing attribute triples "
                         "deleted from the store before retrieval.")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(out_dir / "experiment.log", mode="w",
                                      encoding="utf-8")])
    LOG.info("AUDIT RUN  config: %s", vars(args))

    variants = [v for v in args.variants.split(",") if v]

    # 1. data -------------------------------------------------------------
    t0 = time.perf_counter()
    bundle = build_dataset(args.triples, seed=args.seed)
    LOG.info("Dataset: %d triples, %d entities (seed=%d, %.2fs)",
             bundle.total_triples, len(bundle.entities), args.seed,
             time.perf_counter() - t0)

    n_1hop = args.queries * 2 // 5
    n_2hop = args.queries * 3 // 10
    n_cross = args.queries - n_1hop - n_2hop
    bench = build_benchmark(bundle, n_1hop=n_1hop, n_2hop=n_2hop,
                            n_cross=n_cross, seed=args.seed + 1)
    LOG.info("Benchmark: %d queries %s (seed=%d)", len(bench.queries),
             dict(Counter(q.category for q in bench.queries)), args.seed + 1)

    # 1b. P6: remove evidence *after* the gold standard is fixed
    if args.missing_evidence > 0:
        n_rm = drop_evidence(bundle.graphs, args.missing_evidence,
                             seed=args.seed + 4)
        LOG.info("P6 missing-evidence=%.2f -> removed %d attribute triples "
                 "(%d left)", args.missing_evidence, n_rm,
                 sum(len(g) for g in bundle.graphs.values()))

    # 2. systems ----------------------------------------------------------
    gt_uris = {u for q in bench.queries for u in q.gt_uris}
    sys_ = build_systems(bundle, exclude_uris=gt_uris, use_llm=args.llm,
                         coverage=args.coverage, noise_seed=args.seed + 2,
                         num_predict=args.num_predict, memory_seed=args.seed + 3,
                         align_error=args.align_error)
    LOG.info("Aligner memory coverage=%.2f (%d/%d entities)",
             args.coverage, sys_.entities_memorised, len(bundle.entities))

    answerer = get_answerer(sys_.graphs, exclude_uris=list(gt_uris))
    judge_proxy = get_judge("mock")          # always: continuity with the paper
    judge_llm = None
    llm_judge_qids: set[str] = set()
    if args.judge == "ollama":
        judge_llm = get_judge("ollama")
        jv = [v for v in args.judge_variants.split(",") if v]
        cats = sorted({q.category for q in bench.queries})
        per = max(1, args.judge_queries // len(cats))
        rng = random.Random(999)
        for c in cats:
            pool = [q.qid for q in bench.queries if q.category == c]
            llm_judge_qids.update(rng.sample(pool, min(per, len(pool))))
        LOG.info("LLM judge enabled on %d query ids for variants %s",
                 len(llm_judge_qids), jv)
        judge_variants = set(jv)
    else:
        judge_variants = set()

    # 3. protocol B (concurrent) -----------------------------------------
    rows, proto = [], []
    df = pd.DataFrame()
    if not args.skip_concurrent:
        rows, proto = run_concurrent(
            sys_, bench.queries, variants, args.workers, answerer, judge_proxy,
            judge_llm, llm_judge_qids, judge_variants,
            args.clear_cache_concurrent)
        df = pd.DataFrame(rows)
        df.to_csv(out_dir / "experimental_results.csv", index=False,
                  encoding="utf-8-sig")

    # 4. protocol A (serial service time) --------------------------------
    if not args.skip_serial:
        proto += run_serial(sys_, bench.queries, variants, args.serial_queries,
                            args.serial_warmup, answerer, judge_proxy)
    pd.DataFrame(proto).to_csv(out_dir / "protocol_matrix.csv", index=False,
                               encoding="utf-8-sig")

    # 5. aggregation ------------------------------------------------------
    if not df.empty:
        agg, percat = aggregate(df, variants)
        agg.to_csv(out_dir / "aggregate_summary.csv", index=False,
                   encoding="utf-8-sig")
        percat.to_csv(out_dir / "per_category.csv", index=False,
                      encoding="utf-8-sig")

    # 6. run configuration + environment ---------------------------------
    cfg = dict(vars(args), store_triples=bundle.total_triples,
               entities=len(bundle.entities),
               graph_a_triples=len(bundle.graphs["A"]),
               graph_b_triples=len(bundle.graphs["B"]),
               queries=len(bench.queries),
               llm_judge_qids=sorted(llm_judge_qids),
               timestamp=time.strftime("%Y-%m-%d %H:%M:%S"))
    cfg.update(env_report())
    (out_dir / "run_config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    LOG.info("Wrote results to %s/", out_dir)
    if not df.empty:
        LOG.info("Fallback (ollama->mock) rates by variant:")
        for _, r in agg.iterrows():
            LOG.info("  %-24s fallback=%d/%d", r.variant,
                     r.backend_mock_fallback, r.n)


if __name__ == "__main__":
    main()
