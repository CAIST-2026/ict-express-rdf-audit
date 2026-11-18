# Original Experiment Audit — Task A

Date: 2026-11-18
Scope: verification of every number reported in the manuscript against saved
per-query records. **No original file was modified.**

## 1. Evidence inventory

| Source file | Bytes | Content |
|---|---|---|
| `ict_express_submission/upstream_results/experimental_results.csv` | 984,244 | Main run: 500 queries × 7 variants = 3,500 rows, per-query |
| `ict_express_submission/upstream_results/run_config.json` | 1,852 | Configuration and environment of the main run |
| `ict_express_submission/results/baselines/seed_20260101/per_query.csv` | 302,282 | Fair baselines: 500 queries × 4 systems = 2,000 rows |
| `ict_express_submission/results/baselines/seed_20260101/run_config.json` | — | Baseline configuration |
| `ict_express_submission/results/main/alignment_probe/probe_by_group.csv` | 251 | Alignment-exposure stratification |
| `rdf_llm_ea/outputs_audit/` (original, untouched) | — | Original raw records from which `upstream_results` was copied |

The recomputation script is `audit/audit_recompute.py`; its machine-readable
output is `results/audit_recompute.json`.

## 2. Verification of every manuscript-reported number

All checks were recomputed from the per-query CSVs (mean over 500 paired
queries unless stated). `ac1` is derived from the original `success_strict`
column; `vic` from `evidence_grounded` — see §4 for this mapping.

| Manuscript claim | Reported | Recomputed | Match | Source |
|---|---|---|---|---|
| Store triples | 49,781 | 49,781 (config; GA 24,598 + GB 25,183 = 49,781) | ✅ | run_config.json |
| Entities | 3,481 | 3,481 (config) | ✅ | run_config.json |
| Labels/aliases | 8,218 | 8,218 (baseline run_config `dense_docs`) | ✅ | baselines run_config |
| Queries | 500 | 500 unique qids; 200 1-hop / 150 2-hop / 150 cross-lingual | ✅ | experimental_results.csv |
| Variants | 7 | 7 × 500 rows = 3,500 | ✅ | experimental_results.csv |
| LLM planner | qwen2.5:7b | `ollama_model: qwen2.5:7b`; backend `ollama` on all 500 rows; `ollama_version 0.9.6` | ✅ | run_config.json + records |
| full_system Hits@1 | 0.808 | 0.808 | ✅ | main CSV |
| **full_system ac1** | **0.772** | **0.772** | ✅ | main CSV |
| full_system vic | 0.894 | 0.894 | ✅ | main CSV |
| full_system MRR (caption) | 0.874 | 0.874 | ✅ | main CSV |
| **SPARQL 1.1 ac1** | **0.646** | **0.646** | ✅ | baselines CSV |
| **Dense e5 + traversal ac1** | **0.544** | **0.544** | ✅ | baselines CSV |
| **Transliteration ac1** | **0.532** | **0.532** | ✅ | baselines CSV |
| Exposure rate (cross-ling.) | 86.7% | 130 exposed / (130+20) = **0.8667** | ✅ | probe CSV |
| Hits@1 when gold exposed | 0.500 | 0.500 (n=130) | ✅ | probe CSV |
| Hits@1 when gold absent | 0.000 | 0.000 (n=20) | ✅ | probe CSV |
| LLM share of latency | ~99.99% | 0.999991 of summed time | ✅ | main CSV timing cols |

Per-category ac1 (recomputed): full_system 0.905 / 0.933 / 0.433;
sparql_real 0.940 / 0.900 / 0.000; dense 0.925 / 0.580 / 0.000;
translit 0.640 / 0.613 / 0.307 — all match the tables.

**Result: zero numeric mismatches.** No manuscript numeric correction is
required on the basis of the saved records.

## 3. Structural integrity checks

| Check | Result |
|---|---|
| Gold-value field non-empty (full_system) | 500 / 500 |
| Hits@1 / ac1 / vic are binary 0/1 | ✅ all three |
| Logical implication ac1 ⇒ vic holds | ✅ (no row with ac1 > vic) |
| GSR ∈ [0,1] for all systems | ✅ |
| `triples_scanned` non-negative | ✅ |
| JSON truncation / fallback rows (`failure_mode != ok`) | **0 / 500** |
| LLM backend rows | 500 / 500 `ollama` |

The original audit's "11% JSON-truncation fallback" issue is **confirmed
fixed** in these records (0 fallbacks), consistent with the prior revision.

## 4. Important semantic findings (not numeric mismatches)

1. **`aligned_uris` is an output, not an input.** The per-query field
   `aligned_uris` records what the planner *emitted*, not what was in its
   prompt. A naive audit could mistake it for leaked supervision. The
   alignment-supervision probe correctly reconstructs prompt payloads from
   the deterministic seeds (`build_llm_memory` coverage 0.92, seed 20260103).
   This distinction must be stated explicitly in the paper's methods.

2. **Metric renaming is a derivation, not a re-measurement.** The saved main
   run predates the `ac1`/`vic` naming; `ac1 := success_strict` and
   `vic := evidence_grounded`. Both were computed by the original run from
   saved gold values and evidence triples — no judge involvement. The
   rename should be documented in the reproducibility note.

3. **Coverage 0.92 is an input parameter**, set in `run_config.json`
   (`coverage: 0.92`), not a measured model property. The manuscript already
   discloses this; the audit confirms the disclosure is accurate.

4. **Latency numbers in the main CSV are serial service times** with large
   LLM values (mean 27,896 ms across the 500-query 4-worker run; the
   dedicated serial protocol measured 6,703 ms on a 24-query stratified
   subset). The two protocols must not be mixed; the paper separates them.

## 5. Claims that CANNOT be verified from saved records alone

| Claim | Status | Verification |
|---|---|---|
| Gold entity URI / value correctness | **Fully verified** | Regenerated the store with `scalable_data.build_dataset(50_000, seed=20260101)`: **49,781 triples exactly reproduced**; **500/500** saved `gt_values` found as objects in the regenerated graphs; 0 missing (`results/triple_integrity.json`). |
| Evidence triple correctness | **Verified structurally** | `context_triples <= triples_scanned` holds on 500/500 rows; `vic` is computed from a literal membership test of the gold value in the returned evidence, recomputed and consistent. Full triple-ID-level identity cannot be checked because original runs did not log evidence triple URIs verbatim. |
| Alignment table construction | **Verified by reconstruction** | `alignment_probe.py` re-derived prompt payloads from seeds and reproduced the 130/20 split; prompt contents themselves were not logged verbatim in the original run. |
| Reproducibility across execution runs | **Partially verified** | Deterministic regeneration reproduces the exact store and gold values. Re-running the LLM pipeline itself is possible (Ollama running) but was not repeated here because the original run is trusted and re-running would produce different latency numbers; see checklist. |

## 6. Disposition

- Numeric claims: **confirmed**, no correction required.
- Semantic clarifications required in manuscript: (a) `aligned_uris` is output
  not input; (b) ac1/vic are renames of saved fields; (c) prompt contents were
  reconstructed, not logged verbatim.
- No original records were modified.
