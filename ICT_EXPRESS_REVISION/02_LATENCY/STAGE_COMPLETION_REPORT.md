# Stage 3 completion report: unified latency workload

**Status:** Completed  
**Gate:** Passed after environment defect correction.

## Work performed

- Replaced the confounded original latency workload with one fixed 24-qid workload (8 per category).
- Ran all executable variants with identical qids, order, warm-up, cache policy, and repeat count.
- Detected that the first run's real-SPARQL zero was caused by missing `pyparsing`; installed the dependency, added a hard SPARQL preflight, and reran the full protocol.
- Validated workload equality programmatically: 6 variants × 24 qids × 2 repeats.
- Computed median-based slowdown contrasts and checked that LLM inference dominates serial service time.

## Key outputs

- `LATENCY_ANALYSIS.md`
- `STAGE_COMPLETION_REPORT.md`
- `results/LATENCY_RAW_RUNS.csv`
- `results/LATENCY_PER_QUERY.csv`
- `results/LATENCY_SUMMARY.csv`
- `results/LATENCY_EXPERIMENT_CONFIG.yaml`
- `results/LATENCY_CONTRASTS.csv`
- `logs/latency_run.log`

## Principal accepted numbers

- full_system median: 8584.218 ms; mean LLM time: 8378.261 ms.
- sparql_real median: 156.704 ms; full_system/sparql_real = 54.8×.
- no_aligner_k6 median: 0.174 ms; full_system/no_aligner_k6 = 49,335×.
- translit median: 0.081 ms; full_system/translit = 105,978×.
- Workload ac1 is descriptive only; accuracy claims remain based on the 500-query benchmark.

## Known limitation

Dense e5 is excluded because torch/transformers are not installed in this environment. This must be stated in the paper and final report rather than filled with an estimated latency.
