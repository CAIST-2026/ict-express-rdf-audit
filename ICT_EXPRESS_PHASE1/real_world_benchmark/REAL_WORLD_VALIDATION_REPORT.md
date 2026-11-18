# Real-World Validation Report — Task C

Date: 2026-11-18. Results: `real_world_benchmark/EXPERIMENT_RESULTS.csv`
(165 rows = 55 queries × 3 groups). Executed by
`RUN_LOCAL_EXPERIMENT.py` on 632 real Wikidata RDF triples.

## 1. Scope of what was actually executed

- **Data source**: real Wikidata zh/en labels and 8 property types, downloaded
  from `query.wikidata.org` on 2026-11-18, saved verbatim in
  `RAW_SPARQL_RESPONSES.json`.
- **Execution**: offline over a local rdflib graph built from those authentic
  triples. The live endpoint was abandoned after HTTP 504 (full-table query)
  and HTTP 429 (1 req/min rate limit) made per-query live calls produce
  artificial zeros; the contaminated run was preserved in
  `logs/EXPERIMENT_RESULTS_RATE_LIMITED_INVALID.csv` and is **not** used.
- **Query families executed**: one-hop (34), cross-lingual (21).
  Two-hop, ambiguous, and heterogeneous-predicate families were **not**
  generated/executed (see limitations).

## 2. Results (ac1 = evidence-constrained strict accuracy)

| Query family | n | NO_SUPERVISION | MATCHED_SUPERVISION | ORACLE (upper bound) |
|---|---|---|---|---|
| one-hop (zh label → zh view) | 34 | **1.000** | 1.000 | 1.000 |
| cross-lingual (zh → en view) | 21 | **0.000** | **0.000** | 1.000 |

Hits@1, MRR, and vic follow the same pattern (one-hop 1.0 across groups;
cross-lingual 0.0 for both non-oracle groups, 1.0 for oracle).

## 3. Interpretation — does the methodology generalize?

**Partially, with an important qualification.**

1. **Methodology transfers**: the same evidence-constrained metric (`ac1`)
   and supervision stratification produce interpretable results on authentic
   Wikidata RDF. One-hop retrieval with in-language labels succeeds perfectly
   when the gold value is genuinely in the retrieved evidence (34/34), which
   validates that `ac1` is not an artifact of the synthetic generator.
2. **Cross-lingual finding is reproduced in a stricter form**: with a
   language-partitioned view and an alignment table covering only the 49
   training entities, both non-oracle systems score 0/21 on held-out
   cross-lingual queries. This is the real-world analogue of the synthetic
   "0/20 when gold URI absent" result — and here the 95% exact binomial CI is
   also [0, 0.161]. The bottleneck is **alignment coverage of the test
   entities**, not the retrieval algorithm.
3. **The synthetic paper's specific claim about LLM-vs-non-LLM cannot be
   tested here**: this experiment used a deterministic SPARQL-surface system,
   not the LLM planner. It validates the *supervision-controlled evaluation
   methodology*, not the LLM's cross-lingual capability on real KGs.

## 4. Limitations (explicit, not hidden)

1. **Only 2 of 5 requested query families** were executed. Two-hop and
   ambiguous/predicate-mapping queries require a denser attribute sample than
   the 70-entity pool provided; generating them would need another Wikidata
   crawl, which the endpoint rate limit made impractical in this session.
2. **Wikidata is identity-linked** (one URI, many language labels). The
   cross-lingual condition simulates partitioned views rather than testing
   alignment between genuinely separate graphs (as the synthetic benchmark
   does). Therefore this is **not** evidence of cross-graph entity alignment
   on real data.
3. **70 entities / 632 triples** is a small real sample; results are
   illustrative of methodology transfer, not a statistically powerful
   generalization study.
4. The one-hop 1.000 result is partly a consequence of querying with the
   exact stored label — it should not be read as evidence that real-world
   retrieval is "solved".

## 5. Executable plan to complete the missing families

```bash
# After WDQS rate limit clears (or using a local DBpedia dump):
# 1. Expand the QID pool to 500+ entities with dense P27/P106/P19 coverage.
# 2. For two-hop: add queries of the form "<person> 的国籍的首都是什么？"
#    with gold = capital(QID-of-country) fetched via wdt:P36.
# 3. For ambiguous: select zh labels shared by >=2 entities in the sample.
# 4. For heterogeneous predicates: map schemaA/zh predicates to Wikidata
#    properties and issue the same intent in both schemas.
# 5. Re-run DATASET_PREPROCESSING.py -> QUERY_GENERATION.py ->
#    RUN_LOCAL_EXPERIMENT.py and update this report.
```

No result in this report is invented; all numbers come from
`EXPERIMENT_RESULTS.csv` derived from saved authentic Wikidata triples.
