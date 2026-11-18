# Phase 1 Reproducibility

Date: 2026-11-18. Working directory: repository root (`ict_express_submission/`).

## 1. Environment

- Python >= 3.11 using the repository's `requirements.txt`. The original
  Phase-1 virtual environment and vendored wheels are not published; the
  helper `env/vendor_install.py` is retained only as a sandbox workaround.
- Dependency versions used in the audit: rdflib 7.6.0, numpy 2.5.5, pandas
  3.1.1, scipy 1.18.1, pypinyin 0.55.0.
- Ollama 0.9.6 at `http://localhost:11434`, model qwen2.5:7b (verified running).
- `torch`/`transformers` and e5 weights are **not** in the Phase-1 env; dense
  baseline re-execution requires them (original results were reused, not re-run).
- Original main run environment (from `run_config.json`): Python 3.11.5,
  rdflib 7.5.0, pandas 3.0.6, numpy 2.4.6, torch 2.14.0.

## 2. Seeds and datasets

| Item | Value |
|---|---|
| Synthetic data / main run seed | 20260101 |
| Benchmark offset | +1 (queries) |
| LLM-memory seed | 20260104 (SEED+3) |
| Memory coverage | 0.92 (input parameter, not measured) |
| LLM | qwen2.5:7b, temperature 0, JSON, num_predict 256 |
| Real-world data | Wikidata Query Service, accessed 2026-11-18, CC0 1.0 |
| Real sample | 70 entities from fixed QID pool in `DATASET_PREPROCESSING.py` |

## 3. Execution commands (in order)

```bash
cd ict_express_submission

# Task A — audit (read-only on originals)
python ICT_EXPRESS_PHASE1/audit/audit_recompute.py > ICT_EXPRESS_PHASE1/results/audit_recompute.json
python ICT_EXPRESS_PHASE1/audit/verify_triples.py          # regenerates 49,781-triple graph

# Task B — matched supervision
python ICT_EXPRESS_PHASE1/baseline_fairness/matched_supervision.py
python ICT_EXPRESS_PHASE1/baseline_fairness/build_comparison.py

# Task C — real-world data (requires network to query.wikidata.org)
python ICT_EXPRESS_PHASE1/real_world_benchmark/DATASET_PREPROCESSING.py
python ICT_EXPRESS_PHASE1/real_world_benchmark/QUERY_GENERATION.py   # provenance only
python ICT_EXPRESS_PHASE1/real_world_benchmark/RUN_LOCAL_EXPERIMENT.py  # authoritative

# Task D — statistics
python ICT_EXPRESS_PHASE1/statistical_verification/stats_verify.py

# Tables
python ICT_EXPRESS_PHASE1/reports/generate_tables.py
```

`QUERY_GENERATION.py` is an early live-endpoint experiment whose output was
invalidated by WDQS rate limiting (HTTP 429); it is retained for provenance
only. **Use `RUN_LOCAL_EXPERIMENT.py` for authoritative real-world numbers.**

## 4. Input files (all read-only)

- `upstream_results/experimental_results.csv` — 3,500 rows
- `results/baselines/seed_20260101/per_query.csv` — 2,000 rows
- `results/main/alignment_probe/probe_by_group.csv`
- `upstream/scalable_data.py`, `upstream/scalable_benchmark.py`, `upstream/engine.py`
- `ICT_EXPRESS_PHASE1/real_world_benchmark/RAW_SPARQL_RESPONSES.json` — authentic Wikidata responses

## 5. Output map

| Output | Produced by |
|---|---|
| `ICT_EXPRESS_PHASE1/results/audit_recompute.json`, `ICT_EXPRESS_PHASE1/results/triple_integrity.json` | Task A scripts |
| `ICT_EXPRESS_PHASE1/baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv`, `BASELINE_COMPARISON_TABLE.csv` | Task B |
| `ICT_EXPRESS_PHASE1/real_world_benchmark/EXPERIMENT_RESULTS.csv` | Task C (offline) |
| `ICT_EXPRESS_PHASE1/statistical_verification/STATISTICAL_RESULTS.csv` | Task D |
| `ICT_EXPRESS_PHASE1/UPDATED_EXPERIMENT_TABLES/TABLE{1..6}_*.csv` | `ICT_EXPRESS_PHASE1/reports/generate_tables.py` |

## 6. Known non-reproducible elements

1. Live WDQS is rate-limited (1 req/min during this session); the sampling
   step (`DATASET_PREPROCESSING.py`) may need retries or a local dump.
2. Re-running the LLM pipeline changes latency values; original latency
   records are preserved and were reused rather than re-measured.
3. The submission package environment (`ict_express_submission/env`) was
   removed at the user's request; it can be rebuilt from its requirements.
