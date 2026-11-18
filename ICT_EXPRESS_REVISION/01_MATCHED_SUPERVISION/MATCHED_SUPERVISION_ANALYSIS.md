# Matched-Supervision Analysis

Date: 2026-11-18. Data:
`results/MATCHED_SUPERVISION_PER_QUERY.csv` (1,500 rows) and
`results/MATCHED_SUPERVISION_STATISTICS.csv` (4 rows).

## 1. Definition of added diagnostics

| Metric | Definition | Denominator | Computable from saved records? |
|---|---|---|---|
| `alignment_coverage` | 1 if the gold URI appears in the reconstructed shared alignment table for the query, else 0 | 1 per query | Yes |
| `alignment_expansion` | `n_aligned / max(1, n_anchors)`; mean >1 means one anchor expands to multiple URIs | per query | Yes |
| `evidence_recall_proxy` | `vic`: gold value literally present in returned evidence | 1 per query | Yes |
| `invalid_uri_count` | planner URIs not matching `http://example.org/kg[AB]/entity/.+` | planner output tokens | Yes |
| `execution_failure` | saved `failure_mode != ok` | queries | Yes (all zero) |
| `error_type` | saved failure mode | queries | Yes (no failures) |
| `predicate_selection_accuracy` | correct predicate constraints / gold constraints | gold predicates | **No** — no plan-level logs |
| `query_planning_success_rate` | valid executable plan / query | queries | **No** — no plan logs beyond `aligned_uris` |
| `invalid_sparql` | malformed SPARQL / generated SPARQL | generated queries | **No** — SPARQL text not saved; SPARQL baseline uses rdflib API |
| Fine-grained error distribution | typed error categories | failed queries | **No** — no failures recorded |

Metrics marked "No" require a new instrumented planner run. They are not
inferred or fabricated here.

## 2. Paired statistics

| Scope | Metric | LLM mean | Non-LLM mean | Difference | 95% bootstrap CI | p (Holm) |
|---|---|---:|---:|---:|---:|---:|
| All 500 | ac1 | 0.772 | 0.498 | +0.274 | [0.230, 0.318] | 1.36e-29 |
| All 500 | vic | 0.894 | 0.908 | -0.014 | [-0.038, 0.008] | 0.473 |
| Cross-lingual 150 | ac1 | 0.433 | 0.433 | 0.000 | [0.000, 0.000] | 1.000 |
| Cross-lingual 150 | vic | 0.827 | 0.867 | -0.040 | [-0.073, -0.013] | 0.043 |

Exact McNemar on cross-lingual ac1: **0 discordant pairs out of 150**. This is
a null result for a difference, **not** evidence of equivalence: no
equivalence margin was pre-specified and no equivalence test was run. The
vic difference is significant after Holm correction, so the two systems are
not identical on every metric.

## 3. Alignment exposure and expansion

| Group | Category | n | alignment_coverage | mean expansion | ac1 | vic |
|---|---|---:|---:|---:|---:|---:|
| MATCHED | 1-hop | 200 | 0.920 | 1.855 | 0.920 | 0.930 |
| MATCHED | 2-hop | 150 | 0.000* | 1.842 | 0.000 | 0.920 |
| MATCHED | cross-lingual | 150 | 0.867 | 1.739 | 0.433 | 0.867 |
| NO_SUPERVISION | cross-lingual | 150 | 0.867* | 1.739 | 0.000 | 0.000 |
| ORACLE | cross-lingual | 150 | 0.867* | 1.739 | 1.000 | 1.000 |

\* For 2-hop, the gold answer is a work URI reached by traversal; the probe
does not apply. For NON-MATCHED groups, `alignment_coverage` is a
counterfactual flag: it says the table *would* have covered the gold URI, but
that information was not supplied to those groups.

## 4. Invalid URIs and failures

- 5 unique queries (1.0% of 500) produce one malformed planner URI each: a
  bare local identifier without the expected HTTP namespace. This appears in
  15/1,500 per-query group rows because the same planner output is reused for
  all three groups.
- 0/3,500 main-run rows have `failure_mode != ok`.
- Two rows have an empty `aligned_uris` field while still marked `ok`; this is
  a logging inconsistency, not a scored execution failure.

## 5. Answer to the central question

- **Cross-lingual alignment:** no LLM advantage is observed under matched
  supervision. Attention should shift to the external alignment table.
- **Overall planning:** the LLM retains a large, statistically significant
  ac1 advantage (+0.274), driven by 1-hop/2-hop planning and predicate
  selection. The available evidence does not isolate how much comes from
  predicate choice alone.
- **Cost:** since cross-lingual ac1 gain is zero under matched supervision,
  LLM inference is not justified for alignment alone; the cost case applies
  only to planning-heavy in-language queries.
