# Original Results Audit — Stage 1

Date: 2026-11-18.
Scope: all numeric claims in `ict_express_submission/paper/main.tex` and the current 6-page PDF.
Method: independent recomputation from saved per-query CSVs by
`recalculate_original_results.py`; output in `ORIGINAL_RESULTS_RECALCULATED.csv`.
No result was copied from the manuscript without recomputation.

## 1. Manuscript identification

The task brief names `main(2).pdf`, but no such file exists anywhere under
`/Users/yuxiangsun/Desktop/ICT`. The operative manuscript is
`ict_express_submission/paper/main.tex` / `main.pdf` (6 pages, commit `79c5d94`).
The original Springer manuscript at `manuscript/manuscript.*` was treated as
historical, not as the revision target.

## 2. Recalculation summary

31 audit rows: **28 MATCH**, **1 TRACEABLE**, **1 REVISED**, **1 MISMATCH**.

- All store, query, main-result, category-result, probe, matched-supervision,
  statistical, and Wikidata numbers reproduce from saved records.
- `Hits@1 = 0.000` for unexposed cross-lingual queries is now reported as
  **0/20 observed successes, exact 95% CI [0, 0.168]**; this was already fixed
  in the current manuscript and is marked REVISED, not MISMATCH.
- The only current MISMATCH is the latency workload: the LLM runs on 24 unique
  qids (48 rows = two protocols), while fast-method variants run on 198 qids
  each with a 210-qid union across variants. There is no common workload in
  the saved records. This is a P0 defect and is carried into Stage 3.

## 3. Resolution of Abstract 0.498

Question in the task brief: where does `0.498` come from, given that the main
table shows transliteration 0.532 and the matched-supervision table shows
0.433 cross-lingual?

**Finding: 0.498 is traceable and correctly used as an overall 500-query ac1.**

| Property | Value |
|---|---|
| Source file | `ict_express_submission/ICT_EXPRESS_PHASE1/baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv` |
| Filter | `group=MATCHED_SUPERVISION`; `system=localized_traversal`; all 500 queries |
| Recomputed ac1 | **0.498** |
| Dataset | Full 500-query benchmark (200 one-hop, 150 two-hop, 150 cross-lingual) |
| Cross-lingual-only ac1 from same system | 0.433333 (150 queries) |
| Not from | original main table, transliteration baseline, or cross-lingual subset |
| Paired contrast in abstract | full LLM system 0.772 vs matched linker 0.498 |
| Paired test | exact McNemar, 151 vs 14 discordant wins, p = 3.39e-30 |

Interpretation: `0.498` is the **overall** accuracy of the deterministic
non-LLM linker when it receives the same alignment table as the LLM. The
abstract compares it with LLM 0.772 to isolate planning/predicate-selection
value. The 0.433 figure answers a different question: cross-lingual accuracy
only, where LLM and non-LLM are identical. These numbers are not contradictory
but the abstract must keep the scopes explicit. The current abstract does so.

## 4. Input/output and metric consistency

- The main run has 3,500 rows = 500 unique qids × 7 variants.
- Corrected baselines have 2,000 rows = same 500 qids × 4 systems.
- Matched supervision has 1,500 rows = 500 qids × 3 groups.
- `ac1` and `vic` are field renames of `success_strict` and
  `evidence_grounded`; the rename is documented in `traceability.csv`.
- `ac1 ⇒ vic` holds for all 500 full-system rows; metrics are binary and GSR
  is within [0,1] for all checked rows.
- `aligned_uris` is a planner **output** field; the prompt input is
  reconstructed by `alignment_probe.py` from fixed seeds.
- Fallback count is 0/500; all main rows show `backend=ollama`.

## 5. Information-leakage observations carried forward

1. The planner prompt contains the truth-derived alias table for 130/150
   cross-lingual queries. This is the central confound addressed by matched
   supervision, not a hidden leak.
2. No serialised alignment table exists; it is reconstructed deterministically.
   Stage 2 must serialise the actual lookup snapshot for audit.
3. Oracle rows are explicitly upper bounds, not deployable baselines.
4. Wikidata native QID identity is hidden by constructing language-partitioned
   views, but the QID mechanism needs an explicit policy document (Stage 4).
5. Predicate-selection labels and plan-level logs are absent from saved records;
   Stage 2 must separate derivable from non-derivable diagnostics.

## 6. Stage 1 verdict

**Passed with one P0 carry-over.** All paper numbers are reproducible and the
0.498 ambiguity is resolved. The mixed latency workload is a genuine P0 defect
that must be fixed before submission. Proceed to Stage 2 and Stage 3; do not
submit while the latency workload remains unfixed.
