# Experimental Claim Audit — Phase 1

| # | Original manuscript claim | Status | Evidence / required action |
|---|---|---|---|
| 1 | 49,781 triples; 3,481 entities; 8,218 labels | **Verified** | Config + regenerated graph (`results/triple_integrity.json`) |
| 2 | 500 queries (200/150/150) | **Verified** | 500 unique qids in saved CSVs |
| 3 | Qwen2.5-7B planner, 0 fallbacks | **Verified** | run_config + 500/500 backend=ollama, failure_mode=ok |
| 4 | full_system ac1 = 0.772 | **Verified** | Recomputed from per-query records |
| 5 | SPARQL 1.1 ac1 = 0.646 | **Verified** | Recomputed from fair-baseline records (1,500 real SPARQL calls) |
| 6 | dense ac1 = 0.544 / translit 0.532 | **Verified** | Recomputed |
| 7 | 86.7% cross-lingual gold URI in prompt | **Verified** | 130/150, probe reconstructs prompts from seeds |
| 8 | Hits@1 = 0.500 when gold exposed | **Verified** | 65/130, exact CI [0.411, 0.589] |
| 9 | "Hits@1 = **exactly** 0.000 when gold absent" | **REVISE** | Observed 0/20; exact 95% CI [0, 0.168]. Zero observed ≠ zero capability. |
| 10 | "all Holm-corrected p<1e-7 on ac1" | **REVISE** | no_aligner/no_aligner_k6 Holm p = 7.85e-4. Say p<1e-3. |
| 11 | "LLM-guided retrieval outperforms SPARQL/dense" | **REVISE** | True only vs *unsupervised* baselines. Under matched alignment table, non-LLM linker matches LLM exactly on cross-lingual (0.4333, 0 discordant pairs). |
| 12 | Cross-lingual ability reflects LLM world knowledge | **UNSUPPORTED** | 0.000→0.4333 when the same table is given to any system; 0/21 real-world held-out queries without table coverage. |
| 13 | "LLM aligns entities across graphs" | **UNSUPPORTED** | LLM selects from `knowledge[key]` supplied in prompt; aligned_uris is an output field. |
| 14 | GSR = measured I/O/memory saving | **UNSUPPORTED** (already removed in current manuscript) | GSR is a logical access ratio; traversal time 0.19 vs 47 ms does not measure I/O. |
| 15 | Real-world validation on DBpedia | **NOT DONE** | DBpedia unreachable; Wikidata used (CC0, authentic RDF); methodology transfer only, no cross-graph alignment. |
| 16 | Two-hop / ambiguous / predicate-mapping real queries | **NOT DONE** | Endpoint 504/429 + limited sample; documented executable plan provided. |
| 17 | LLM latency dominance (~99.99%) | **Verified** | 0.999991 of summed serial time; separate 24-query protocol 6,703 ms mean. |
| 18 | Pruning = pure cost lever | **Verified** | Identical ac1 (p=1), GSR 3.65e-4→1.0, traversal 0.19→47 ms. |

**Disposition:** no numeric correction needed; five claim revisions (#9, #10,
#11, #12, #13) and two scope statements (#15, #16) must be incorporated before
submission.
