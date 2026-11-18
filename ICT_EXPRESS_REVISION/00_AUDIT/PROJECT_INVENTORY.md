# Project Inventory — ICT Express Systematic Revision

Date: 2026-11-18. Scope: read-only inventory of `/Users/yuxiangsun/Desktop/ICT`.
No original file was modified, moved, or deleted. Machine-readable index:
`PROJECT_INVENTORY.csv` (659 files; SHA-256 recorded for files <20 MB).

## 1. Manuscript files

| Item | Path | Status |
|---|---|---|
| Operative manuscript (PDF) | `ict_express_submission/paper/main.pdf` | Present; Elsevier `cas-dc`, 6 pages, compiled 2026-11-18 |
| Operative source | `ict_express_submission/paper/main.tex` | Present; current submitted version |
| Original 23-page Springer manuscript | `manuscript/manuscript.tex`, `manuscript/manuscript.pdf` | Present; read-only historical source |
| Springer template bundle | `sn-article-template/` | Present; not used by current ICT Express submission |
| **`main(2).pdf` named in task brief** | — | **Missing.** No file with this name exists anywhere under the project root. The operative `paper/main.pdf` is treated as the current manuscript. |

The task brief's `main(2).pdf` discrepancy is recorded as an audit finding; all
number checks below use `ict_express_submission/paper/main.tex` and its compiled PDF.

## 2. Experiment code

| Category | Present artefacts |
|---|---|
| Core original pipeline | `rdf_llm_ea/engine.py`, `scalable_data.py`, `scalable_benchmark.py`, `judge.py`, `baselines_extra.py` |
| Original runners | `rdf_llm_ea/run_audit_experiment.py`, `run_comprehensive_experiment.py`, `run_baselines.py`, `run_experiment.py`, `scaling_audit.py`, `stats_tests.py` |
| Corrected submission scripts | `ict_express_submission/experiments/*.py` (metrics, alignment probe, fair baselines, latency, scaling, transliteration diagnosis, statistics, summarisation) |
| Phase 1 audit scripts | `ICT_EXPRESS_PHASE1/audit/*.py`, `baseline_fairness/*.py`, `real_world_benchmark/*.py`, `statistical_verification/*.py` |
| Figure/table generation | `ict_express_submission/experiments/summarize.py`; `ICT_EXPRESS_PHASE1/reports/generate_tables.py` |

## 3. Data, queries, and alignment material

| Item | Status |
|---|---|
| Synthetic RDF generator / seed | Present (`scalable_data.py`, `SEED=20260101`); regenerates 49,781 triples |
| 500-query benchmark | Present (`scalable_benchmark.py`; saved per-query records in `upstream_results/experimental_results.csv`) |
| Alignment lookup table | **No standalone file.** Constructed deterministically at runtime by `build_llm_memory(coverage=0.92, seed=SEED+3)` and the `label_to_key → knowledge → alias_index` path. This is an audit finding: a serialised snapshot should be added in this revision. |
| Prompt reconstruction | Present (`experiments/alignment_probe.py`) |
| Real Wikidata raw responses | Present (`ICT_EXPRESS_PHASE1/real_world_benchmark/RAW_SPARQL_RESPONSES.json`, `entities.json`, `attributes.json`, `QUERIES.json`) |
| DBpedia material | Absent; DBpedia endpoints/dumps were unreachable. Documented in Phase 1 report. |

## 4. Per-query records and result CSVs

| Dataset | Path | Rows / scope |
|---|---|---|
| Main run | `ict_express_submission/upstream_results/experimental_results.csv` | 3,500 = 500 queries × 7 variants |
| Corrected baselines | `ict_express_submission/results/baselines/seed_20260101/per_query.csv` | 2,000 = 500 × 4 systems |
| Alignment probe | `ict_express_submission/results/main/alignment_probe/probe_per_query.csv` | 500 queries |
| Latency | `ict_express_submission/results/latency/per_query.csv` | 24-query LLM subset + 198-query fast methods |
| Scaling | `ict_express_submission/results/scaling/scaling.csv` | 10K/50K/100K/200K triples |
| Statistics | `ict_express_submission/results/stats/pairwise_tests.csv` | paired tests on saved runs |
| Matched supervision | `ICT_EXPRESS_PHASE1/baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv` | 1,500 = 500 × 3 groups |
| Real Wikidata | `ICT_EXPRESS_PHASE1/real_world_benchmark/EXPERIMENT_RESULTS.csv` | 165 = 55 queries × 3 groups |
| Phase 1 published tables | `ICT_EXPRESS_PHASE1/UPDATED_EXPERIMENT_TABLES/TABLE{1..6}_*.csv` | 6 publication tables |

## 5. Logs, configs, and provenance

- `ict_express_submission/traceability.csv` maps reported numbers to source files.
- `ict_express_submission/results/**/run_config.json` records seeds and arguments.
- `ICT_EXPRESS_PHASE1/logs/` preserves the rate-limited Wikidata run (`EXPERIMENT_RESULTS_RATE_LIMITED_INVALID.csv`), audit stderr, and Ollama server log.
- `ICT_EXPRESS_PHASE1/reports/` contains the Phase 1 final report, claim audit, reproducibility checklist, and changelog.
- GitHub release: `https://github.com/CAIST-2026/ict-express-rdf-audit`, branch `main`, clean and synchronised at commit `79c5d94`.

## 6. Missing or weak evidence (carried into audits)

1. `main(2).pdf` does not exist; operative manuscript identified as above.
2. No serialised alignment table snapshot; only deterministic reconstruction code.
3. No predicate-selection labels or plan-level logs in saved per-query records; several requested matched-supervision diagnostic metrics cannot be computed retrospectively without a new instrumented run.
4. Original `/ict_express_submission/env` was removed at the user's request; dependencies must be rebuilt from `requirements.txt`.
5. Live Wikidata endpoint is rate-limited (HTTP 429); authoritative real-RDF results use saved authentic responses offline.
6. Unified latency workload across all methods is not yet present; existing Table 4 mixes 24-query LLM and 198-query fast-method workloads. This is a P0 item for the current revision.
7. Related work is currently 8 references; expansion and verification is required.

## 7. Inventory verdict

All core synthetic-benchmark and Phase 1 artefacts are present and traceable.
The workspace is sufficient to begin P0 audits. The missing named PDF, absent
alignment snapshot, mixed latency workload, and incomplete real-world coverage
are explicit audit findings rather than blockers to starting Stage 1.
