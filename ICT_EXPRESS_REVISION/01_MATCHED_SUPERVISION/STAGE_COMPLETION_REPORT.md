# STAGE_COMPLETION_REPORT — Stage 2: Matched-Supervision Fairness and Leakage

Date: 2026-11-18.

## Completed work

- Serialised the deterministic alignment table used by planner prompts and
  matched-supervision controls.
- Audited six leakage channels: prompt gold exposure, alignment-table test
  answers, candidate generation, query rewriting, oracle isolation, and
  LLM/non-LLM supervision parity.
- Added per-query diagnostics: alignment coverage, expansion, evidence recall,
  invalid URI count, execution failure, and explicit nulls for non-computable
  predicate/SPARQL metrics.
- Recomputed paired statistics with McNemar exact, Wilcoxon, paired bootstrap
  CI, and Holm correction.

## Data and code

- Inputs: Phase 1 matched-supervision CSV, main-run CSV, regenerated memory
  tables from `SEED=20260101`, `MEM_SEED=20260104`, coverage 0.92.
- Code: `code/alignment_leakage_audit.py`.
- Environment: Phase 1 audit Python 3.13.12 with pandas/numpy/scipy.

```bash
/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_PHASE1/env/bin/python \
  01_MATCHED_SUPERVISION/code/alignment_leakage_audit.py
```

## Generated files

- `data/alignment_snapshot.json`
- `results/MATCHED_SUPERVISION_PER_QUERY.csv` (1,500 rows)
- `results/MATCHED_SUPERVISION_STATISTICS.csv` (4 rows)
- `ALIGNMENT_LEAKAGE_AUDIT.md`
- `MATCHED_SUPERVISION_ANALYSIS.md`

## Core results

- Overall ac1: LLM 0.772 vs matched linker 0.498; difference +0.274,
  95% CI [0.230, 0.318], Holm p = 1.36e-29.
- Cross-lingual ac1: 0.433 vs 0.433; 0/150 discordant pairs; not an
  equivalence claim.
- Cross-lingual vic: 0.827 vs 0.867, Holm p = 0.043; systems are not identical
  on all metrics.
- 5/500 queries (1.0%) produce a malformed planner URI token.
- 0/3,500 main rows have a recorded execution failure.

## Unresolved issues

- Predicate-selection accuracy, planning success rate, invalid-SPARQL rate,
  and fine-grained error types cannot be computed from saved records; they
  require instrumented re-runs.
- The LLM receives richer natural-language profiles than the non-LLM linker;
  alignment information is matched, planner machinery is not.

## Gate decision

**Stage 2 passed.** The central fairness finding is supported and now has a
serialised alignment snapshot. Proceed to Stage 3 (unified latency workload),
which remains a P0 blocker for submission.
