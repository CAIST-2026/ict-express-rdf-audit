# WIKIDATA_ALIGNMENT_POLICY

## 1. QID identity mechanism

In Wikidata, a QID is the stable identifier of an entity, for example `Q1150` is serialized locally as `http://www.wikidata.org/entity/Q1150`. Multilingual labels are language-tagged values attached to the **same** URI:

```text
<entity/Q1150> rdfs:label "墨丘利"@zh .
<entity/Q1150> rdfs:label "Mercury"@en .
```

Direct properties are PIDs, serialized as `http://www.wikidata.org/prop/direct/P106` for occupation, etc. Gold object QIDs in the saved attributes are normalized to full entity URIs before scoring; gold English labels are compared literally against the retrieved evidence set.

## 2. Why this is not cross-graph entity alignment

The synthetic benchmark uses two graphs with different URIs for the same person and no identity link. Wikidata does not have that structure. Its zh/en labels are alternative labels of one entity. Therefore:

- the real benchmark can test cross-language access under a **language-partitioned view**;
- it cannot test alignment between two independently managed graphs;
- the word “alignment” in the real experiment refers only to a train-pool zh-label→URI lookup table, not to discovery of `owl:sameAs` or equivalent identity links.

## 3. Train/held-out split

```python
split = max(1, int(len(entities) * 0.7))   # 49 of 70
train = entities[:split]                   # QID list order from saved data
test = entities[split:]                    # 21 held-out QIDs
train_zh2uri = {e["zh"]: e["uri"] for e in train}
```

The split is deterministic and uses the order of the saved entity list. All 21 held-out cross-lingual queries use subjects from `test`; no held-out gold zh→URI mapping is inserted into `MATCHED_SUPERVISION`.

## 4. Supervision conditions

| Condition | Input | Purpose |
|---|---|---|
| `NO_SUPERVISION` | Query mention + target-language label index only | Lower bound without alignment bridge |
| `MATCHED_SUPERVISION` | Same as above + train-pool zh→URI table | Tests alignment coverage; test entries are absent by design |
| `ORACLE` | Gold URI directly | Upper bound; not a deployable baseline |

Rows using the oracle carry `test_gold_used_as_input=true`. This flag prevents accidental interpretation of oracle performance as a system result.

## 5. Cross-lingual view construction

For cross-lingual queries, the mention is the Chinese label but the surface index exposed to the system contains only English labels. This models two platforms that expose one language each. A matched alignment entry is the only allowed bridge.

- Train subjects: 49/49 receive the bridge; matched ac1 = 1.000.
- Held-out subjects: 0/21 receive the bridge; matched ac1 = 0.000, exact 95% CI [0.000, 0.161].
- Two surface-identical labels (`Megaupload`, `YouTube`) succeed without a bridge; they are reported as lexical overlaps, not alignment successes.

## 6. Prohibited claims

Do not write that the Wikidata experiment:

- validates real cross-graph entity alignment;
- measures the LLM planner on real data;
- establishes a general success rate for real multilingual RDF retrieval;
- proves that cross-lingual capability is exactly zero, given the small held-out sample.

Allowed claim: the same evidence-constrained metrics and supervision-stratified audit protocol behave as expected on authentic Wikidata RDF, and expose alignment coverage as the binding constraint in the language-partitioned condition.
