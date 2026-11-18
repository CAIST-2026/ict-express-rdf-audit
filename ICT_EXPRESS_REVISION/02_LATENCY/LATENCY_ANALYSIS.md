# Unified latency analysis

## 1. Protocol actually executed

- Workload: 24 fixed qids, 8 per category (1-hop, 2-hop, cross-lingual).
- Every variant used exactly the same qids, fixed order, 2 warm-up queries, and 2 timed repeats.
- Cache policy: LLM plan cache cleared before each repeat.
- Workers: 1; queueing not included.
- Metric: per-query wall-clock service time in milliseconds. Throughput is reported only as an internal consistency check, not as a loaded-QPS claim.
- Dense e5 was excluded because torch/transformers are not installed in this execution environment. This is recorded as an environment limitation, not a performance result.

Workload equality was checked programmatically by `validate_unified_latency.py`; output in `results/LATENCY_CONTRASTS.csv`.

## 2. Environment defect found and corrected

The first execution produced `sparql_real` ac1 = 0.000 because rdflib's SPARQL parser dependency `pyparsing` was missing and `RealSparqlBaseline` caught the resulting exception. That run was discarded before analysis. `pyparsing 3.3.3` was installed, a hard SPARQL preflight was added to the experiment script, and the full protocol was rerun. The accepted run reports a non-zero real-SPARQL latency and accuracy, confirming that the earlier zero was an environment failure rather than an algorithm result.

## 3. Accepted results

| Variant | n qids | Runs | Median ms | Mean ms | p95 ms | Mean LLM ms | ac1 on workload |
|---|---:|---:|---:|---:|---:|---:|---:|
| full_system | 24 | 48 | 8584.218 | 8378.576 | 9673.866 | 8378.261 | 0.792 |
| no_aligner_k6 | 24 | 48 | 0.174 | 0.192 | 0.363 | 0.000 | 0.667 |
| sparql_baseline | 24 | 48 | 0.139 | 0.148 | 0.232 | 0.000 | 0.333 |
| vector_graphrag | 24 | 48 | 2.408 | 2.583 | 5.061 | 0.000 | 0.500 |
| sparql_real | 24 | 48 | 156.704 | 289.580 | 605.531 | 0.000 | 0.542 |
| translit | 24 | 48 | 0.081 | 0.086 | 0.126 | 0.000 | 0.500 |

Median-based slowdowns:

- full_system vs no_aligner_k6: 49,335×
- full_system vs sparql_baseline: 61,757×
- full_system vs vector_graphrag: 3,565×
- full_system vs sparql_real: 54.8×
- full_system vs translit: 105,978×

The LLM component accounts for 8,378.261 of 8,378.576 ms mean service time (99.996%), so the latency gap is attributable to model inference rather than traversal.

## 4. Interpretation

This experiment fixes the P0 workload confound in the original latency table: all six executable variants now share one 24-query workload. The results support a cost statement, not an accuracy ranking: the LLM dominates serial service time by roughly 1.7--5 orders of magnitude depending on the comparator, while real SPARQL is about two orders of magnitude slower than localized traversal but still ~55× faster than the LLM pipeline on this workload.

The 24-query `ac1` column is descriptive. It should not replace the 500-query accuracy results, because this subset was selected for balanced categories and latency feasibility, not as an accuracy sample.

## 5. Files

- `results/LATENCY_RAW_RUNS.csv` — 288 timed per-query runs.
- `results/LATENCY_PER_QUERY.csv` — 144 per-query aggregates.
- `results/LATENCY_SUMMARY.csv` — accepted variant-level summary.
- `results/LATENCY_EXPERIMENT_CONFIG.yaml` — protocol and environment record.
- `results/LATENCY_CONTRASTS.csv` — validated workload and median slowdowns.
- `logs/latency_run.log` — accepted run log.
