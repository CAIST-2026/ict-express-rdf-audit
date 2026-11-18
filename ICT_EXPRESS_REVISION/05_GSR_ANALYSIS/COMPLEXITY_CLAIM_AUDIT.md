# GSR and Complexity Claim Audit

Date: 2026-11-18. Data: `results/GSR_REANALYSIS.csv` and
`results/GSR_REGRESSION_RESULTS.csv`, recomputed from the saved scaling CSV.

## 1. What GSR actually measures

\[
\mathrm{GSR}(q)=\frac{|S(q)|}{|T|},
\]

where \(|S(q)|\) is the number of **logically scanned triples** recorded by the
executor and \(|T|\) is the store size. GSR is a logical access ratio. It is
not measured disk I/O, memory allocation, cache behaviour, or overall
algorithmic complexity.

## 2. Reanalysis

| Variant | Mean triples scanned, 10K → 200K | log-log exponent on scanned count | R² |
|---|---|---:|---:|
| full_system | 17.5 → 17.8 (peak 19.3) | 0.015 | 0.195 |
| no_predicate_constraint | 15.8 → 14.5 (peak 16.0) | -0.019 | 0.293 |
| no_aligner_k6 | 10.5 → 16.5 | 0.163 | 0.900 |
| vector_graphrag | 41.5 → 44.9 | 0.030 | 0.648 |
| sparql_real | 1,531 → 31,347 | 1.006 | 1.000 |
| no_pruning | equals |T| | 1.000 | 1.000 |

GSR exponents near -1 for localized variants are largely a **denominator
effect**: \(|S(q)|\) stays roughly stable while \(|T|\) grows 20-fold. This is
consistent with, but does not prove, a bounded logical-access policy.

## 3. Confounds and limitations

1. The scaling script selects subsets with `seed=11 + size % 97`, so the exact
   query IDs differ across graph sizes. Comparisons are not paired.
2. LLM variants use only 6 queries per size; fast methods use 99.
3. A fixed access budget in `OptimizedExecutor` can mechanically stabilise
   \(|S(q)|\); this must be described as a design choice, not discovered
   asymptotic behaviour.
4. No hardware counters, page faults, cache misses, or allocator measurements
   were collected.
5. Real SPARQL latency grows close to linearly (log-log exponent 0.992, R²
   0.998), whereas full-system latency stays flat because the LLM call
   dominates. This is an observed runtime profile of one implementation and
   machine, not a general complexity theorem.

## 4. Claim disposition

| Existing / potential claim | Status | Required wording |
|---|---|---|
| "GSR decreases as $|T|^{-1}$" | Descriptive, acceptable with formula | Keep only as empirical fit of the ratio |
| "Logical access stays $O(1)$" | Overclaim | Replace with: "the observed number of logically accessed triples remains approximately stable under the evaluated graph-size scaling conditions" |
| "Overall query complexity is $O(1)$" | Unsupported | Do not use |
| "GSR proves I/O or memory savings" | Unsupported | Do not use; report traversal time only as supplementary evidence |
| "Localized pruning reduces logical access by ~3 orders at 50K" | Supported | Keep, explicitly as logical access |

## 5. Gate decision

**Stage 6 passed for claim correction.** No new scaling experiment was needed
to reject the overclaim; the saved data already show the denominator effect.
The manuscript must adopt the restricted wording above.
