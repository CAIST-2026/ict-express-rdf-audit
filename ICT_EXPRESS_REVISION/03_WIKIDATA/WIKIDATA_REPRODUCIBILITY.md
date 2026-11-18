# WIKIDATA_REPRODUCIBILITY

## 1. One-shot rebuild

```bash
/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_PHASE1/env/bin/python \
  /Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_REVISION/03_WIKIDATA/code/build_wikidata_benchmark.py
```

The script reads only files under `ICT_EXPRESS_PHASE1/real_world_benchmark/` and writes only under `ICT_EXPRESS_REVISION/03_WIKIDATA/`. It does not contact the Wikidata endpoint.

## 2. Inputs

| File | SHA-256 |
|---|---|
| `raw_data/WIKIDATA_RAW_SPARQL_RESPONSES.json` | `6d03419c906b830098933f8b41ca502552d7b5088559cf37944199852eadf99f` |
| `processed_data/WIKIDATA_ENTITIES.json` | `4f85747d0145264348eb73db08892979d8747da4f8ab468b63c15a968b2e25f0` |
| `processed_data/WIKIDATA_ATTRIBUTES.json` | `fdf1da60f2945390749d8c0f3d79196c50474a490099b21abc68547fb8d207a6` |

Environment used for the recorded run: Python 3.13, pandas, scipy 1.18.1, rdflib 7.x from `ICT_EXPRESS_PHASE1/env`.

## 3. Outputs

```text
queries/WIKIDATA_QUERY_SET.csv              184 rows
queries/WIKIDATA_GOLD_ANSWERS.csv           184 rows
results/WIKIDATA_PER_QUERY_RESULTS.csv      552 rows
results/WIKIDATA_EXPERIMENT_RESULTS.csv      39 rows
logs/wikidata_build.log                     recorded console output
```

## 4. Determinism

- The train split is `int(70 * 0.7) = 49` on the saved entity order.
- Query IDs are assigned in a fixed loop order: first 70 cross-lingual queries, then 114 one-hop entity–predicate pairs.
- No sampling, shuffling, or model inference is used.
- Exact confidence intervals use `scipy.stats.beta.ppf` with the two-sided Clopper–Pearson construction.

## 5. Known scope limits

The live WDQS endpoint was rate-limited in Phase 1; the expanded benchmark therefore reuses saved authentic responses. Two-hop, ambiguity, and heterogeneous-predicate families were not added because the necessary chained properties were not present in the saved sample. This is a documented data-coverage limit, not a hidden omission.
