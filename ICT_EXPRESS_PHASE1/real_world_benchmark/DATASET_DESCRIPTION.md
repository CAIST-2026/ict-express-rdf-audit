# Real-World Dataset Description — Task C

Date: 2026-11-18

## 1. Source selection and availability

| Candidate | URL | Status |
|---|---|---|
| DBpedia EN SPARQL | `https://dbpedia.org/sparql` | Unreachable from this environment (empty response / SSL) |
| DBpedia ZH SPARQL | `https://zh.dbpedia.org/sparql` | SSL_ERROR_SYSCALL, HTTP 000 |
| DBpedia dumps | `https://downloads.dbpedia.org/`, `datadumps.dbpedia.org` | SSL_ERROR_SYSCALL, HTTP 000 |
| **Wikidata Query Service** | `https://query.wikidata.org/sparql` | **HTTP 200, real zh/en RDF labels returned** |
| Hugging Face | `https://huggingface.co` | HTTP 200 (not used) |

**Decision:** DBpedia is unavailable in this environment. Per the task brief
("Other publicly available bilingual RDF datasets if more appropriate"),
Wikidata is used as the real-world source. It is a genuine multilingual RDF
knowledge graph with authentic labels and properties — not synthetic data.

## 2. Dataset facts (recorded, not assumed)

- **Source**: Wikidata Query Service, `https://query.wikidata.org/sparql`
- **Access date**: 2026-11-18
- **License**: Wikidata data is CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/)
- **Language pair**: Chinese (`zh`) / English (`en`) labels on the SAME entity URI
  (Wikidata is identity-linked; the cross-lingual challenge here is *label
  access across language views*, not entity identity — see §5).
- **Sample**: 70 unique real entities from a fixed QID pool (`DATASET_PREPROCESSING.py`);
  28 of them have 8 property types (P27 citizenship, P106 occupation, P19
  birthplace, P20 deathplace, P1412 language, P69 educated at, P108 employer,
  P463 member of).
- **Local RDF graph**: 632 triples (`rdflib Graph`: 140 bilingual labels +
  492 property triples), built verbatim from saved SPARQL responses.
- **Raw responses**: `RAW_SPARQL_RESPONSES.json` contains the exact queries and
  full JSON responses (98 KB), preserving provenance.

## 3. Preprocessing

1. Two-phase lightweight SPARQL (a full-table `ORDER BY` query timed out with
   HTTP 504; a fixed QID `VALUES` query succeeded and is reproducible).
2. Entity deduplication by QID → 70 unique bilingual entities.
3. Attribute batch query over 8 predicates → `attributes.json`.
4. Split: first 49 entities = **alignment-training pool**; remaining 21 =
   **held-out test** (their gold zh↔en mappings are never used as model input
   in unsupervised or matched-supervision conditions).
5. Local rdflib graph construction from saved triples (labels typed with
   `@zh` / `@en` language tags) — makes the experiment offline-reproducible
   and immune to WDQS rate limiting (HTTP 429, 1 req/min during this session).

## 4. Query families (`QUERIES.json`, 55 queries)

| Family | n | Construction | Gold |
|---|---|---|---|
| one-hop | 34 | Chinese label + predicate question (e.g. 黎剎的国籍是什么？) | Real object QIDs from `attributes.json` |
| cross-lingual | 21 | Chinese mention; retrieval restricted to English-label view | Same entity URI + its English label as gold value |

The original brief requested 5 families (one-hop, two-hop, cross-lingual,
ambiguous, heterogeneous-predicate). **Only 2 families were executed** —
two-hop/ambiguous/predicate-mapping generation was not completed because of
the endpoint 504/429 constraints and the limited attribute coverage of the
small sample. This gap is documented, not silently skipped.

## 5. Critical caveat — what this benchmark does and does not test

Wikidata uses a **single URI per entity** with multilingual labels. Unlike the
synthetic benchmark (two graphs, different URIs, no `owl:sameAs`), there is no
cross-graph identity gap to bridge. The cross-lingual condition here tests
**cross-language label retrieval under a partitioned view** (a simulation of
two platforms that expose only one language each), NOT entity alignment
between independently managed graphs. Consequently:

- The real-world experiment validates the **evaluation methodology**
  (evidence-constrained metrics, supervision stratification, oracle bounds).
- It does **not** validate the claim that the pipeline aligns entities across
  heterogeneous graphs in the wild.
- The "alignment table" in the real experiment is a zh→URI map from the train
  pool; when test entities are absent from it (as designed), neither LLM nor
  non-LLM can cross the language gap — consistent with the synthetic finding
  that coverage, not reasoning, bounds cross-lingual performance.

## 6. Data leakage controls

- Test gold URIs/labels are used **only** for scoring and in the ORACLE group
  (explicitly labelled `test_gold_used_as_input=true` in results).
- The train-alignment map is built from the first 49 entities only; every
  test entity is verified disjoint (`assert` in both generation and execution
  scripts).
- No query text contains its own gold URI.
