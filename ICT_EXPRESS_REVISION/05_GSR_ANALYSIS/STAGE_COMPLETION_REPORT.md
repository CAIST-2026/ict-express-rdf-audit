# GSR Analysis — Stage 6

Date: 2026-11-18.

## Completed work

- Recomputed mean GSR, mean scanned triples, traversal time, end-to-end time,
  and ac1 for every variant at 10K/50K/100K/200K triples.
- Refitted log-log exponents for GSR, scanned-triple count, and runtime.
- Audited the complexity language in the manuscript.

## Commands

```bash
/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_PHASE1/env/bin/python \
  05_GSR_ANALYSIS/code/gsr_reanalysis.py
```

## Generated files

- `results/GSR_REANALYSIS.csv` (28 rows)
- `results/GSR_REGRESSION_RESULTS.csv` (21 rows)
- `COMPLEXITY_CLAIM_AUDIT.md`

## Core findings

- full_system scans 17.5–19.3 triples on average across a 20× store-size range;
  its scanned-count exponent is 0.015 with R²=0.195 (no reliable growth trend).
- The near -1 GSR exponent is therefore mostly caused by the growing
  denominator |T|, not by a measured improvement in hardware cost.
- no_aligner_k6 shows a mild increase (10.5→16.5 scanned triples); claims of a
  perfectly constant access budget are too strong.
- Real SPARQL scanned triples scale ~linearly (exponent 1.006) and runtime
  ~linearly (exponent 0.992), while full-system runtime is flat because the
  LLM dominates.

## Unresolved issues

- Query subsets differ across sizes; no paired scaling experiment was run.
- Only 6 LLM-timed queries per size.
- No hardware-level I/O/memory counters.

## Gate decision

**Passed with manuscript wording changes required.** Replace O(1) complexity
language with the observed-stability statement documented in
`COMPLEXITY_CLAIM_AUDIT.md`.
