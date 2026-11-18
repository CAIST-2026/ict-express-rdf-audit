# FINAL_EXPERIMENT_REPORT

## 1. Executed work

This revision executed a full audit chain rather than rewriting claims first:

1. **Original-result audit:** 31 numeric assertions rechecked; 28 MATCH, 1 TRACEABLE (`0.498`), 1 REVISED (0/20 exact CI), 1 MISMATCH (old latency workload).
2. **Matched-supervision leakage audit:** serialized the deterministic alignment table; confirmed that gold URI exposure in planner prompts is a known confound, not a hidden leak.
3. **Unified latency:** reran all executable variants on the same 24 qids with fixed order, warm-up, cache policy, and two timed repeats. A first real-SPARQL zero caused by missing `pyparsing` was discarded; dependency fixed, preflight added, and experiment rerun.
4. **Wikidata:** audited QID/PID identity mechanism; expanded from 55 to 184 queries from saved authentic triples; executed supervision-controlled local experiment.
5. **Statistics:** consolidated paired tests, Holm correction, Wilson/exact/bootstrap CIs, effect sizes, and figure-generation code.
6. **GSR:** reanalysed scaling and removed the unsupported O(1) complexity claim.
7. **Related work:** verified 19 references against authoritative records; corrected two DOI/page errors in the manuscript.

## 2. Key accepted numbers

| Claim | Evidence |
|---|---|
| `0.498` | Full-benchmark ac1 of matched deterministic traversal, not cross-lingual subset |
| LLM overall advantage | 0.772 vs 0.498; diff CI [0.230, 0.318]; Holm p=1.36e-29 |
| Cross-lingual parity under matched table | 0.433 vs 0.433; 0/150 discordant; not equivalence |
| Unexposed cross-lingual probe | 0/20; exact CI [0, 0.168] |
| Real SPARQL (500-query) | ac1 0.646; Holm p=3.19e-8 |
| Unified latency | full median 8,584 ms; real SPARQL median 157 ms; translit median 0.081 ms |
| Wikidata transfer | 114 one-hop ac1 1.000; cross-lingual matched 49/70; held-out 0/21 |
| GSR scaling | scanned triples 17.5--19.3 over 20× graph sizes; no O(1) claim |

## 3. Failed or excluded elements

- DBpedia endpoints were unreachable; Wikidata was used as the authentic RDF substitute.
- Dense e5 was excluded from unified latency because torch/transformers were unavailable; its 500-query accuracy remains reported.
- Wikidata two-hop, ambiguity, and heterogeneous-predicate families were not generated because the saved sample lacks the required chained properties and live WDQS was rate-limited.
- The first unified-latency `sparql_real` result was invalid due to an environment dependency and was discarded.

## 4. Reproducibility

All accepted result files, scripts, configs, logs, and hashes are in `ICT_EXPRESS_REVISION/`. The GitHub release is `v2.0` at commit `37cab3e`; the final paper commit is `4c30ec6`.
