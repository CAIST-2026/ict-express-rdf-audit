# STAGE_COMPLETION_REPORT — Stage 1: Original Experiment and Paper Audit

Date: 2026-11-18.

## Completed work

- Created `ICT_EXPRESS_REVISION/` with all requested stage directories.
- Generated a read-only inventory of 659 project files with SHA-256 hashes.
- Identified the operative manuscript and recorded that `main(2).pdf` is absent.
- Independently recomputed 31 manuscript claims from saved per-query CSVs.
- Resolved the Abstract `0.498` question with source file, filter, sample size,
  and paired significance test.
- Confirmed zero numeric mismatches for all main/result/probe/matched/Wikidata
  claims; recorded one P0 latency-workload defect and one revised CI claim.

## Data used

- `ict_express_submission/upstream_results/experimental_results.csv` (3,500 rows)
- `ict_express_submission/results/baselines/seed_20260101/per_query.csv` (2,000 rows)
- `ict_express_submission/results/main/alignment_probe/probe_by_group.csv`
- `ict_express_submission/ICT_EXPRESS_PHASE1/baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv`
- `ict_express_submission/ICT_EXPRESS_PHASE1/statistical_verification/STATISTICAL_RESULTS.csv`
- `ict_express_submission/ICT_EXPRESS_PHASE1/real_world_benchmark/EXPERIMENT_RESULTS.csv`
- `ict_express_submission/results/latency/per_query.csv`

## Code and commands

New script: `00_AUDIT/recalculate_original_results.py`.
Inventory script: `00_AUDIT/build_inventory.py`.

```bash
python3 00_AUDIT/build_inventory.py
/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_PHASE1/env/bin/python \
  00_AUDIT/recalculate_original_results.py
```

Environment: original audit virtualenv (Python 3.13.12, pandas 3.1.1,
numpy 2.5.5, scipy 1.18.1) because system `python3` has no pandas/numpy.

## Generated files

- `00_AUDIT/PROJECT_INVENTORY.md`
- `00_AUDIT/PROJECT_INVENTORY.csv`
- `00_AUDIT/ORIGINAL_RESULTS_AUDIT.md`
- `00_AUDIT/ORIGINAL_RESULTS_RECALCULATED.csv` (31 rows)
- `00_AUDIT/REPRODUCIBILITY_CHECKLIST.md`
- `00_AUDIT/build_inventory.py`
- `00_AUDIT/recalculate_original_results.py`

## Core results

- 28 claims MATCH, 1 TRACEABLE (`0.498`), 1 REVISED (exact CI), 1 MISMATCH
  (latency workload).
- `0.498` = full-benchmark ac1 of `localized_traversal` under
  `MATCHED_SUPERVISION`, n=500; cross-lingual subset is 0.433 (n=150).
- Abstract contrast 0.772 vs 0.498: McNemar exact p=3.39e-30 (151 vs 14).
- Latency workload: full_system 24 unique qids; fast methods 198 qids each,
  union 210. No shared workload.

## Verification

All numbers were recomputed by the new independent script rather than copied.
The `0.498` result was traced to exact CSV filter and then independently
paired against the LLM run by qid.

## Unresolved issues

1. P0: unified latency workload missing (Stage 3).
2. Serialised alignment table missing (Stage 2).
3. Plan-level diagnostics missing (Stage 2).
4. Wikidata identity/QID policy needs explicit documentation (Stage 4).
5. `main(2).pdf` absent; operative manuscript substituted.

## Gate decision

**Stage 1 passed with a P0 carry-over.** Proceed to Stages 2–3. Do not proceed
to final submission or paper-only polishing while the latency defect remains.
