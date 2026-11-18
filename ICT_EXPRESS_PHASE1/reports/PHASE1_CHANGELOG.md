# Phase 1 Changelog

Date: 2026-11-18

## Code modifications

All Phase-1 code is NEW, under `ICT_EXPRESS_PHASE1/`. No original file was
modified. One supporting tool (`vendor_install.py`) was copied from
`ict_express_submission/experiments/` into `ICT_EXPRESS_PHASE1/env/` and its
wheel-tag list extended with `macosx_12_0_arm64` / `macosx_14_0_arm64` so
scipy 1.18.1 could be installed on this interpreter.

## Executed experiments

1. **Audit recomputation** (`audit/audit_recompute.py`) — all manuscript
   numbers recomputed from 3,500+2,000 saved per-query rows. Output:
   `results/audit_recompute.json`. Exit 0.
2. **Graph regeneration + triple integrity** (`audit/verify_triples.py`) —
   rebuilt 49,781 triples from seed 20260101; 500/500 gold values verified.
   Output: `results/triple_integrity.json`. Exit 0.
3. **Matched-supervision experiments** (`baseline_fairness/matched_supervision.py`)
   — 500 queries × 3 groups = 1,500 rows. Two implementation bugs found and
   fixed during execution (URIRef/str mismatch; alignment lookup missing the
   canonical-key path). Output: `MATCHED_SUPERVISION_RESULTS.csv`. Exit 0.
4. **Comparison table** (`baseline_fairness/build_comparison.py`) — 28 rows.
5. **Real-world data acquisition** (`real_world_benchmark/DATASET_PREPROCESSING.py`)
   — 70 authentic Wikidata entities, 28 with attributes, 55 queries; SPARQL
   responses saved verbatim. Exit 0.
6. **Real-world live experiment** (`QUERY_GENERATION.py`) — **INVALIDATED**:
   WDQS HTTP 429 (1 req/min) produced artificial zeros. Moved to
   `logs/EXPERIMENT_RESULTS_RATE_LIMITED_INVALID.csv`. Not used.
7. **Real-world offline experiment** (`RUN_LOCAL_EXPERIMENT.py`) — 165 rows on
   632 authentic triples. Multiple bugs found/fixed (QID-vs-URI evidence
   mismatch; global-vs-language-partitioned label index; cross-lingual query
   direction). Final output: `EXPERIMENT_RESULTS.csv`. Exit 0.
8. **Statistical verification** (`statistical_verification/stats_verify.py`) —
   43 rows including exact binomial CIs. Exit 0.
9. **Publication tables** (`reports/generate_tables.py`) — 6 CSV tables.

## Newly generated files (by directory)

- `audit/`: `audit_recompute.py`, `ORIGINAL_EXPERIMENT_AUDIT.md`,
  `REPRODUCIBILITY_CHECKLIST.md`, `verify_triples.py`
- `baseline_fairness/`: `matched_supervision.py`, `build_comparison.py`,
  `MATCHED_SUPERVISION_RESULTS.csv`, `BASELINE_COMPARISON_TABLE.csv`,
  `BASELINE_FAIRNESS_ANALYSIS.md`
- `real_world_benchmark/`: `DATASET_DESCRIPTION.md`, `DATASET_PREPROCESSING.py`,
  `QUERY_GENERATION.py`, `RUN_LOCAL_EXPERIMENT.py`, `EXPERIMENT_RESULTS.csv`,
  `REAL_WORLD_VALIDATION_REPORT.md`, `entities.json`, `attributes.json`,
  `QUERIES.json`, `RAW_SPARQL_RESPONSES.json`
- `statistical_verification/`: `stats_verify.py`, `STATISTICAL_RESULTS.csv`,
  `STATISTICAL_VERIFICATION_REPORT.md`
- `results/`: `audit_recompute.json`, `triple_integrity.json`
- `logs/`: `EXPERIMENT_RESULTS_RATE_LIMITED_INVALID.csv` (invalid, preserved)
- `reports/`: `PHASE1_FINAL_REPORT.md`, `EXPERIMENT_REPRODUCIBILITY.md`,
  `EXPERIMENTAL_CLAIM_AUDIT.md`, `generate_tables.py`
- `UPDATED_EXPERIMENT_TABLES/`: `TABLE1_AUDIT_VERIFICATION.csv`,
  `TABLE2_MATCHED_SUPERVISION_CROSS.csv`, `TABLE3_OVERALL_COMPARISON.csv`,
  `TABLE4_PAIRED_TESTS.csv`, `TABLE5_EXACT_CI_UNEXPOSED.csv`,
  `TABLE6_REAL_WORLD.csv`

## Unresolved issues

1. SPARQL/dense **matched-supervision** variants were not executed (no
   torch/transformers in Phase-1 env; no SPARQL+alignment wrapper implemented).
2. Non-LLM traversal's 2-hop ranker is simplified (vic 0.92, ac1 0) — it
   understates a tuned non-LLM system; cross-lingual conclusion unaffected.
3. Real-world benchmark covers only 2 of 5 requested query families; Wikidata
   is identity-linked (no cross-graph alignment gap).
4. Live WDQS rate limiting (HTTP 429/504) — offline local graph used instead.
5. Five manuscript claim revisions identified but NOT applied — Phase 1
   explicitly excludes manuscript rewriting.
