# Statistical Verification Report — Task D

Date: 2026-11-18. All numbers recomputed from saved per-query CSVs by
`statistical_verification/stats_verify.py`; machine-readable output:
`statistical_verification/STATISTICAL_RESULTS.csv` (43 rows).

## 1. Methods verified

- **McNemar exact test** on paired binary outcomes (hits1, ac1), two-sided
  binomial tail on discordant pairs; n=500 paired queries per contrast.
- **Wilcoxon signed-rank** on paired GSR differences (continuous), zero
  differences excluded.
- **Holm step-down correction** applied within each metric family (9 contrasts
  for hits1, 9 for ac1, 9 for GSR).
- **95% Wilson score intervals** for each system's ac1.
- **Exact Clopper–Pearson binomial CI** for the small (n=20) unexposed
  cross-lingual stratum.

## 2. Principal comparisons (ac1, McNemar exact, Holm-adjusted)

| Contrast vs full (0.772) | n | Discordant | Raw p | Holm p | OR | 95% CI (contrast ac1) |
|---|---|---|---|---|---|---|
| no_aligner / no_aligner_k6 | 500 | 94 | 2.62e-4 | **7.85e-4** | 2.22 | [0.658, 0.739] |
| no_predicate_constraint | 500 | 154 | 2.56e-27 | 2.05e-26 | 9.69 | [0.476, 0.564] |
| no_pruning | 500 | 0 | 1.0 | 1.0 | — | [0.733, 0.807] |
| vector_graphrag (legacy) | 500 | 179 | 1.35e-21 | 9.48e-21 | 5.32 | [0.482, 0.569] |
| sparql_baseline (legacy) | 500 | 224 | 1.38e-40 | 1.24e-39 | 10.54 | — |
| dense (e5 + traversal) | 500 | 166 | 4.34e-20 | 2.60e-19 | 5.30 | — |
| dense_ne (no traversal) | 500 | 239 | 1.51e-44 | 1.51e-43 | 11.31 | — |
| sparql_real | 500 | 121 | 7.98e-9 | **3.19e-8** | 3.14 | — |
| translit | 500 | 188 | 1.92e-19 | 9.62e-19 | 4.48 | — |

Full system 95% Wilson CI for ac1: **[0.733, 0.807]** (386/500).

**Correction required:** the manuscript states "all Holm-corrected p<1e-7 on
ac1". This is false for the `no_aligner`/`no_aligner_k6` contrasts
(Holm p = 7.85e-4) and only marginal for `sparql_real` (3.19e-8, which does
satisfy <1e-7). Wording must become "all p<1e-3; p<1e-7 for all fair-baseline
and predicate-constraint contrasts" or similar.

## 3. The 20 unexposed cross-lingual queries — critical correction

| Stratum | n | Observed Hits@1 | Exact 95% CI (Clopper–Pearson) | Wilson 95% CI |
|---|---|---|---|---|
| Gold URI in prompt | 130 | 0.500 | [0.411, 0.589] | [0.415, 0.585] |
| Gold URI absent | 20 | 0.000 | **[0.000, 0.168]** | [0.000, 0.161] |

**Interpretation:** 0/20 successes is consistent with a true success
probability anywhere from 0 up to ≈16.8%. The data do **not** establish that
the pipeline's capability is exactly zero when alignment is absent; they
establish a tight upper bound of ~17% at 95% confidence. The manifest text
"exactly 0.000 when it is not [exposed]" must be qualified as "0/20 observed
(95% CI [0, 0.168])" wherever it appears in the abstract, Section 3, and
conclusion.

This is the single most important statistical correction of Phase 1.

## 4. GSR (paired Wilcoxon, Holm-adjusted)

- `no_pruning`: full GSR 3.65e-4 vs 1.0, mean diff −0.9996, Holm p=4.79e-83 —
  pruning reduces logical access by ~3 orders of magnitude.
- `sparql_real`: full 3.65e-4 vs 0.156, mean diff −0.1556, Holm p=7.10e-83.
- `no_predicate_constraint`: tied on 149/500 pairs, still Holm p=1.17e-32.
- All contrasts significant after Holm; see CSV for full table.

## 5. Sample-size and assumption notes

- n=500 paired queries: adequate for detecting the observed effect sizes;
  McNemar's exact test does not rely on asymptotic approximation.
- The **n=20** unexposed stratum is small — hence the exact CI in §3. Any
  claim about this stratum must carry the interval.
- Queries within the benchmark are not independent samples of a deployment
  population; all inference is conditional on this synthetic benchmark.
- Repeated queries across systems are **paired**, never treated as independent
  samples; the scripts align rows by `qid`.
- Multiple-comparison correction: Holm within metric families; the two
  binomial CIs in §3 are descriptive, not tests, and are not corrected.

## 6. Reproducibility

```bash
cd ict_express_submission
python ICT_EXPRESS_PHASE1/statistical_verification/stats_verify.py
```

Input files are read-only; the script writes only
`ICT_EXPRESS_PHASE1/statistical_verification/STATISTICAL_RESULTS.csv`.
