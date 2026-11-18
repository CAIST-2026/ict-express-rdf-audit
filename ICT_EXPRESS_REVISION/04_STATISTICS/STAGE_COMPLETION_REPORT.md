# Stage 5 completion report: statistical framework enhancement

**Status:** Completed  
**Gate:** Passed.

## Work performed

- Consolidated Phase 1 paired tests, revision matched-supervision tests, alignment-probe strata, expanded Wikidata results, and unified latency results into one harmonized table.
- Recomputed alignment-probe C stratified by category, preventing the 2-hop unexposed stratum from being incorrectly merged with the 20 cross-lingual queries.
- Produced effect-size table including odds ratios, mean differences, proportions, medians, and a clearly labelled descriptive odds-to-r transform.
- Produced a confidence-interval table covering Wilson/exact/bootstrap intervals.
- Added deterministic bootstrap intervals for the unified serial-service latency medians.
- Generated two SVG figures entirely from saved result files.

## Outputs

- `STATISTICAL_ANALYSIS.md`
- `STAGE_COMPLETION_REPORT.md`
- `code/build_statistics_package.py`
- `FIGURE_GENERATION_CODE/make_figures.py`
- `results/STATISTICAL_RESULTS.csv` (69 rows)
- `results/EFFECT_SIZE_RESULTS.csv` (85 rows)
- `results/CONFIDENCE_INTERVAL_RESULTS.csv` (39 rows)
- `results/figures/accuracy_ci.svg`
- `results/figures/latency_median.svg`

## Principal conclusions carried forward

- Full-system ac1 advantage is statistically clear overall, but cross-lingual parity under matched supervision must not be described as equivalence.
- The 0/20 unexposed cross-lingual result carries exact CI [0, 0.168].
- Holm-corrected wording in the manuscript must remain “all accuracy contrasts p < 1e-3; fair-baseline contrasts p ≤ 3.2e-8”.
- Latency comparisons are valid only as serial service-time comparisons on the unified 24-query workload.
