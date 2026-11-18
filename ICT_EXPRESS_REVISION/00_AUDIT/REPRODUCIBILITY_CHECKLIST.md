# Reproducibility Checklist — ICT Express Revision

Date: 2026-11-18. Scope: current operative manuscript and released package.

## Environment

- OS observed in original run config: macOS 27.2 arm64, 8 CPUs, 24 GiB RAM.
- Original main run: Python 3.11.5, rdflib 7.5.0, pandas 3.0.6, numpy 2.4.6,
  torch 2.14.0, matplotlib 3.10.0, Ollama 0.9.6, qwen2.5:7b.
- Phase 1 audit env: Python 3.13.12, rdflib 7.6.0, numpy 2.5.5, pandas 3.1.1,
  scipy 1.18.1, pypinyin 0.55.0. The virtualenv itself is not published;
  rebuild from `ict_express_submission/requirements.txt`.
- Dense encoder: `intfloat/multilingual-e5-small` (or `E5_MODEL_PATH`).

## Fixed seeds and inputs

| Item | Value |
|---|---|
| Synthetic data seed | 20260101 |
| Benchmark offset | +1 |
| Simulated memory seed | SEED + 3 = 20260104 |
| Memory coverage | 0.92 (input parameter, not measured) |
| LLM decoding | temperature 0, JSON, `num_predict=256` |
| Main queries | 500 (200/150/150) |
| Wikidata sample | 70 entities, 632 triples, 55 queries, saved authentic responses |

## One-command reproduction (from `ict_express_submission/`)

```bash
python experiments/baselines_ict.py --out results/baselines/seed_20260101 \
    --systems sparql_real,translit,dense,dense_ne
python experiments/alignment_probe.py \
    --results upstream_results/experimental_results.csv \
    --out results/main/alignment_probe
python experiments/stats_ict.py \
    --main upstream_results/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/stats
python experiments/latency_ict.py --n 24 --out results/latency
python experiments/scaling_ict.py \
    --sizes 10000 50000 100000 200000 --llm-n 8 --fast-n 100 --out results/scaling
python experiments/translit_diagnosis.py \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/diagnostics
python experiments/summarize.py --main upstream_results/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --probe results/main/alignment_probe/probe_by_group.csv \
    --latency results/latency/protocol_summary.csv \
    --scaling results/scaling/scaling.csv \
    --stats results/stats --out .

python ICT_EXPRESS_PHASE1/audit/audit_recompute.py > ICT_EXPRESS_PHASE1/results/audit_recompute.json
python ICT_EXPRESS_PHASE1/audit/verify_triples.py
python ICT_EXPRESS_PHASE1/baseline_fairness/matched_supervision.py
python ICT_EXPRESS_PHASE1/baseline_fairness/build_comparison.py
python ICT_EXPRESS_PHASE1/statistical_verification/stats_verify.py
python ICT_EXPRESS_PHASE1/reports/generate_tables.py
python ICT_EXPRESS_PHASE1/real_world_benchmark/RUN_LOCAL_EXPERIMENT.py
```

The LLM server and e5 weights are required only for LLM/dense timing and
prediction runs; saved per-query records are sufficient for all audits.

## Known non-reproducible or environment-sensitive elements

1. Live WDQS rate limiting (HTTP 429); authoritative real-RDF numbers use saved
   authentic SPARQL responses offline.
2. Latency values depend on local Ollama server state; original records are
   preserved but a unified workload is required (Stage 3).
3. No serialised alignment snapshot; only deterministic reconstruction code
   (Stage 2 must add one).
4. No plan-level predicate labels; predicate-selection accuracy cannot be
   recomputed from saved records (Stage 2 must state this explicitly).
5. Published GitHub release: commit `79c5d94`, clean and synchronised.

## Checklist status

| Item | Status |
|---|---|
| Fixed seeds | ✓ |
| Per-query records | ✓ |
| Source code for all main numbers | ✓ |
| Traceability index | ✓ |
| Environment notes | ✓ |
| Serialised alignment table | ✗ — Stage 2 |
| Unified latency workload | ✗ — Stage 3 |
| Expanded Wikidata | ✗ — Stage 4 |
| Verified 18–25 references | ✗ — Stage 7 |
