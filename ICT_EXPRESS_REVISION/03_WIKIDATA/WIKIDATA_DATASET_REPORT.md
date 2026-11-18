# WIKIDATA_DATASET_REPORT

## 1. Provenance

The revision benchmark is built only from the authentic Wikidata SPARQL responses saved in Phase 1. No new live Wikidata query was issued in this stage.

- Source endpoint: `https://query.wikidata.org/sparql`
- Access date recorded in Phase 1: 2026-11-18
- Raw response file: `raw_data/WIKIDATA_RAW_SPARQL_RESPONSES.json`
- SHA-256: `6d03419c906b830098933f8b41ca502552d7b5088559cf37944199852eadf99f`
- Derived entities: `processed_data/WIKIDATA_ENTITIES.json`
- SHA-256: `4f85747d0145264348eb73db08892979d8747da4f8ab468b63c15a968b2e25f0`
- Derived attributes: `processed_data/WIKIDATA_ATTRIBUTES.json`
- SHA-256: `fdf1da60f2945390749d8c0f3d79196c50474a490099b21abc68547fb8d207a6`

DBpedia endpoints and dumps were unreachable in Phase 1 (empty/SSL failures or HTTP 000), so Wikidata remains the real-world substitute. This is a methodology-transfer check, not a deployment study.

## 2. Recorded dataset facts

| Item | Value |
|---|---|
| Entities with zh/en labels | 70 |
| Entities with saved direct properties | 28 |
| Property types | P27, P106, P19, P20, P1412, P69, P108, P463 |
| Label triples | 140 |
| Property triples | 492 |
| Total local RDF triples | 632 |
| License | Wikidata data, CC0 1.0 |
| URI namespace | `http://www.wikidata.org/entity/Q...` |
| Property namespace | `http://www.wikidata.org/prop/direct/P...` |

The 70 entities come from a fixed QID list in the saved SPARQL `VALUES` clause. This is a purposive, reproducible sample, not a random sample of Wikidata.

## 3. Expanded query set

The Phase 1 set contained 55 queries (34 one-hop, 21 cross-lingual). The revision set is expanded deterministically from the same saved triples:

| Family | n | Construction |
|---|---:|---|
| one-hop | 114 | Every saved `(entity, property)` pair for the 28 attribute-bearing entities; gold values are the saved object QIDs |
| cross-lingual | 70 | All 70 entities; Chinese label mention, English-label view, gold value is the saved English label |
| Total | 184 | 129 train-pool subjects, 55 held-out subjects |

Files:
- `queries/WIKIDATA_QUERY_SET.csv`
- `queries/WIKIDATA_GOLD_ANSWERS.csv`

The expansion adds no unsaved property values or invented answers. Two-hop, ambiguity, and heterogeneous-predicate families remain unexecuted because the saved sample lacks the necessary chained properties and the live endpoint was rate-limited; the reason is recorded rather than silently ignored.

## 4. What was executed

A deterministic local surface/alignment experiment was run over the 632 saved triples:

- `NO_SUPERVISION`: exact mention lookup in the target-language label view only.
- `MATCHED_SUPERVISION`: same lookup, plus a train-pool zh→URI alignment entry when available.
- `ORACLE`: gold URI supplied directly; upper bound only.

Per-query results: `results/WIKIDATA_PER_QUERY_RESULTS.csv` (552 rows = 184 queries × 3 groups).
Aggregates: `results/WIKIDATA_EXPERIMENT_RESULTS.csv` (39 rows).

## 5. Principal results

| Slice | Group | n | ac1 | 95% exact CI |
|---|---|---:|---:|---|
| one-hop, all | no supervision | 114 | 1.000 | [0.968, 1.000] |
| cross-lingual, all | no supervision | 70 | 0.029 | [0.003, 0.099] |
| cross-lingual, all | matched supervision | 70 | 0.700 | [0.579, 0.804] |
| cross-lingual, all | oracle | 70 | 1.000 | [0.949, 1.000] |
| cross-lingual, held-out | no supervision | 21 | 0.000 | [0.000, 0.161] |
| cross-lingual, held-out | matched supervision | 21 | 0.000 | [0.000, 0.161] |
| cross-lingual, held-out | oracle | 21 | 1.000 | [0.839, 1.000] |
| cross-lingual, train | matched supervision | 49 | 1.000 | [0.927, 1.000] |

The two non-oracle cross-lingual successes over all 70 queries are `Megaupload` and `YouTube`, whose saved zh and en labels are identical surface strings. They are not evidence of learned cross-lingual alignment.

## 6. Interpretation boundary

This benchmark validates the evaluation protocol and the alignment-coverage mechanism on authentic RDF. It does **not** validate cross-graph entity alignment on real data, because Wikidata uses one URI per entity with multilingual labels. The language-partitioned view simulates two platforms exposing different label languages; it does not create independently managed graphs with different identities. The deterministic surface system also does not test the LLM planner.
