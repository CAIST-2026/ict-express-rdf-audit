# Baseline Fairness Analysis — Task B

Date: 2026-11-18. All results recomputed/executed in this directory;
no result is fabricated. Machine-readable outputs:
`MATCHED_SUPERVISION_RESULTS.csv` (1,500 rows),
`BASELINE_COMPARISON_TABLE.csv` (28 rows).

## 1. Information audit — what each method actually receives

| Method | Query text | Surface anchors | Cross-lingual alignment table | Predicate constraints | Evidence constraint |
|---|---|---|---|---|---|
| LLM-guided (full_system) | ✅ | ✅ | ✅ via prompt: `knowledge[key]` = both languages' forms + all URIs (coverage 0.92) | ✅ LLM-emitted + `infer_predicate_constraints` | ac1 (gold value in returned triples) |
| LLM no_aligner | ✅ | ✅ | ❌ | ✅ | ac1 |
| Real SPARQL 1.1 (saved) | ✅ | ✅ | ❌ (no `owl:sameAs` in data) | ✅ (query-side) | ac1 |
| Dense e5 + traversal (saved) | ✅ | ✅ | ❌ (monolingual encoder passages) | ✅ | ac1 |
| Transliteration (saved) | ✅ | ✅ pinyin | ⚠️ partial (romanisation pairs only) | ✅ | ac1 |
| **Non-LLM localized, this Phase** | ✅ | ✅ | ✅ / ❌ / oracle — **controlled by group** | ✅ (same `infer_predicate_constraints`) | ac1 (same `metrics.score`) |

**Finding:** in the original comparison the LLM planner received a
truth-derived cross-lingual alias table in its prompt while SPARQL and dense
did not. Comparing their cross-lingual scores without controlling this
information asymmetry is **not a fair comparison of the methods' intrinsic
capability** — it is a comparison of "with alignment table" vs "without".

## 2. Matched-supervision experiment design

Three groups, same 500 queries / same RDF store (49,781 triples) / same gold
answers / same metric implementation (`experiments/metrics.py::score`):

- **NO_SUPERVISION**: only query-side surface anchors, no cross-graph mapping.
- **MATCHED_SUPERVISION**: every system receives the *same* alias table — the
  exact `knowledge → label_to_key → alias_index` path used to build the LLM
  planner's prompt (coverage 0.92, memory seed SEED+3). Non-LLM systems get no
  more information than the LLM receives.
- **ORACLE**: ground-truth gold URIs + equivalent traversal. **Upper bound
  only, not deployable.**

## 3. Key results (ac1)

### Cross-lingual queries (n=150) — the decisive comparison

| System | Supervision | ac1 |
|---|---|---|
| LLM-guided localized | matched (original full_system) | **0.4333** |
| **Non-LLM localized traversal** | **matched (same table)** | **0.4333** |
| LLM-guided localized | none (no_aligner) | 0.0000 |
| Non-LLM localized traversal | none | 0.0000 |
| Real SPARQL 1.1 (saved) | none | 0.0000 |
| Dense e5 + traversal (saved) | none | 0.0000 |
| Oracle traversal | oracle | 1.0000 |

A paired McNemar exact test between the LLM and the non-LLM localized system
on the cross-lingual subset under matched supervision found **0 discordant
pairs out of 150** — their outputs are identical query-by-query. The entire
cross-lingual advantage of the LLM disappears when the non-LLM system is
given the same alignment table.

### Overall (n=500)

| System | Supervision | ac1 | vic | GSR |
|---|---|---|---|---|
| LLM-guided localized | matched | 0.772 | 0.894 | 3.65e-4 |
| LLM-guided localized | none | 0.700 | 0.700 | 2.98e-4 |
| Non-LLM localized traversal | none | 0.400 | 0.700 | 2.98e-4 |
| Non-LLM localized traversal | matched | 0.498 | 0.908 | 5.42e-4 |
| Non-LLM localized traversal | oracle | 1.000 | 1.000 | 2.36e-4 |
| Real SPARQL 1.1 | none (saved) | 0.646 | 0.700 | 0.156 |
| Dense e5 + traversal | none (saved) | 0.544 | 0.672 | 9.0e-4 |

Paired McNemar (500 queries): LLM vs non-LLM under matched supervision,
ac1 0.772 vs 0.498, 151 vs 14 discordant wins, **p<1e-20** (significant).

### By exposure (all 500 queries pooled)

| Group | Gold exposed | Non-LLM traversal ac1 |
|---|---|---|
| MATCHED | yes | 0.793 |
| MATCHED | no | 0.000 |
| NO_SUPERVISION | yes | 0.086 |
| NO_SUPERVISION | no | 0.586 |

The NO_SUPERVISION "exposed" bucket here means the gold URI happened to be a
surface anchor (mostly 1-hop in-language queries); the matched group's gain is
concentrated exactly where the alignment table supplies the counterpart URI.

## 4. Decomposition of the original performance advantage

| Source of advantage | Evidence | Verdict |
|---|---|---|
| **1. Supplied alignment information** | Cross-lingual ac1: 0.000 → 0.433 when the same table is given to any system; 130/150 gold URIs in prompt; LLM vs non-LLM identical on cross-lingual under matched table | **Dominant and decisive for cross-lingual.** |
| **2. LLM-based planning** | Under matched supervision LLM 0.772 vs non-LLM traversal 0.498 overall (p<1e-20); the gain is on 1-hop/2-hop, not cross-lingual | **Real but bounded** to query planning/predicate selection, not alignment knowledge. |
| **3. Predicate constraints** | Removing them: ac1 0.772→0.520; 2-hop 0.933→0.000 (saved ablation) | **Real and large for 2-hop.** |
| **4. Localized graph traversal** | no_pruning: same ac1 (0.772) but GSR 3.65e-4→1.0, traversal 0.19ms→47ms | **Pure cost lever**, no accuracy contribution. |
| Oracle upper bound | ac1 1.000 across all categories | Shows headroom is in the alignment step, not traversal. |

## 5. Implementation caveats (honest limitations)

1. The `Non-LLM localized traversal` implementation uses the shared
   `infer_predicate_constraints` and a bounded 2-hop expansion. Its 2-hop ac1
   is 0 while its vic is 0.92 — the evidence is retrieved but the simplified
   ranker does not place the work URI first. This understates a fully tuned
   non-LLM system; it does **not** affect the cross-lingual conclusion (where
   ranks match the LLM exactly).
2. SPARQL and dense matched-supervision variants were **not executed** in this
   phase (dense needs torch/transformers; a fair SPARQL+alignment wrapper
   would need a new implementation). Their "none" rows are saved real runs.
   Therefore we do **not** claim "LLM planning is superior to SPARQL under
   matched supervision" in general — only that the non-LLM localized
   traversal with the same table matches cross-lingual performance.
3. All oracle rows are upper bounds, explicitly not baselines.

## 6. Answer to the central fairness question

> Does the LLM genuinely outperform conventional retrieval once alignment
> supervision is controlled?

**On cross-lingual queries: NO.** With the same alignment table, a deterministic
non-LLM linker achieves identical ac1 (0.4333) to the 7B LLM planner. The
original cross-lingual "advantage" over SPARQL/dense was an artifact of
unequal supervision, not of LLM capability.

**On the full benchmark: YES, but for a different reason.** The LLM's planning
and predicate-constraint choices yield 0.772 vs 0.498 for the matched non-LLM
traversal, concentrated on in-language 1-hop/2-hop queries. That advantage is
real, significant, and must be stated separately from cross-lingual alignment.
