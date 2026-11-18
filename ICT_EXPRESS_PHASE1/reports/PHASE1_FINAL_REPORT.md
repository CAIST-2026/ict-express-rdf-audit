# Phase 1 Final Report

Date: 2026-11-18. Role: senior researcher + strict ICT Express reviewer.
Scope: experimental audit, baseline fairness, real-world RDF validation,
statistical verification. No manuscript rewriting was performed.

## Executive summary

The original experimental framework is **internally reliable** (all reported
numbers recompute exactly from saved records; 500/500 gold values verified
against a regenerated 49,781-triple graph) but its **central cross-lingual
comparison was not fair**: the LLM planner received a truth-derived alignment
table in its prompt while SPARQL/dense baselines did not. Under matched
supervision the cross-lingual advantage of the LLM **disappears completely**
(a deterministic non-LLM linker achieves identical 0.4333 ac1, 0 discordant
pairs out of 150). The LLM retains a real but narrower advantage on overall
query planning (0.772 vs 0.498, p<1e-20). Real-world Wikidata validation
partially supports the methodology but cannot validate cross-graph alignment.

## Task A — original experiment audit

- **All reported numbers verified**: store/entity/query counts, 7 variants,
  full_system ac1 0.772, SPARQL 0.646, dense 0.544, translit 0.532, exposure
  86.7%, 0.500/0.000 conditional Hits@1, LLM latency share 99.999%. Zero
  numeric mismatches (`audit/ORIGINAL_EXPERIMENT_AUDIT.md`).
- **Gold/evidence verified semantically**: regenerated store reproduces exactly
  49,781 triples; 500/500 gold values found as RDF objects; 0 structural
  violations (`results/triple_integrity.json`).
- **Fallback fixed**: 0/500 JSON-truncation fallbacks in the audited run.
- Three clarifications needed in the manuscript (aligned_uris is output not
  input; ac1/vic are field renames; prompt contents reconstructed).

## Task B — baseline fairness (highest priority)

Decisive result (all systems, same graph/queries/gold/metric):

| Condition | Cross-lingual ac1 | Overall ac1 |
|---|---|---|
| LLM, matched alignment table | 0.4333 | 0.772 |
| **Non-LLM traversal, SAME table** | **0.4333** | 0.498 |
| LLM, no alignment table | 0.0000 | 0.700 |
| Non-LLM traversal, no table | 0.0000 | 0.400 |
| SPARQL 1.1 / dense (saved, no table) | 0.0000 | 0.646 / 0.544 |
| Oracle (upper bound only) | 1.0000 | 1.0000 |

- On the 150 cross-lingual queries, LLM and non-LLM outputs are **identical
  query-by-query** (0 discordant pairs) when given the same table.
- Decomposition: supplied alignment = decisive for cross-lingual; LLM planning
  = real advantage on 1-hop/2-hop; predicate constraints = large (2-hop
  0.933→0.000 when removed); localized traversal = pure cost lever (GSR
  3.65e-4 vs 1.0, identical accuracy).
- Caveats: the non-LLM 2-hop ranker is simplified (vic 0.92 but ac1 0);
  SPARQL/dense matched-supervision variants were not executed. Therefore
  "LLM superior to SPARQL under matched supervision" is **not** claimed.

## Task C — real-world validation

- DBpedia endpoints/dumps unreachable (SSL/HTTP 000); used Wikidata
  (CC0, real zh/en RDF), 70 entities / 632 triples, 55 queries (one-hop +
  cross-lingual only), authentic SPARQL responses preserved.
- Results: one-hop ac1 1.000 (all groups); cross-lingual 0.000 for both
  non-oracle groups because the train-only alignment map does not cover held-out
  test entities; oracle 1.000.
- **What it supports**: methodology transfers to authentic RDF; alignment
  coverage — not reasoning — bounds cross-lingual performance (same finding as
  synthetic, in stricter form).
- **What it does not support**: cross-graph entity alignment on real KGs
  (Wikidata is identity-linked); two-hop/ambiguous/predicate-mapping families
  were not executed. First live-endpoint run was invalidated by WDQS HTTP 429
  rate limiting (preserved in `logs/`, never used).

## Task D — statistical verification

- All McNemar exact / Wilcoxon / Holm / Wilson CIs recomputed
  (`statistical_verification/STATISTICAL_RESULTS.csv`, 43 rows).
- **Two corrections required**:
  1. "all Holm p<1e-7 on ac1" is false for `no_aligner` contrasts
     (Holm p = 7.85e-4). Use "all p<1e-3; p<1e-7 for fair baselines".
  2. "0.000 when gold absent" must be qualified: 0/20 observed, **exact
     95% CI [0, 0.168]** — zero successes do not prove zero capability.
- Full system ac1 95% Wilson CI [0.733, 0.807].

## Task E — research questions

**RQ1 — Does the LLM genuinely outperform conventional methods when alignment
supervision is controlled?** On cross-lingual: **NO** (identical to non-LLM
with the same table). On overall planning: **YES** (0.772 vs 0.498 for matched
non-LLM traversal, p<1e-20), but this is planning/predicate selection, not
alignment knowledge.

**RQ2 — How much cross-lingual performance is from supplied alignment vs
autonomous reasoning?** Effectively **all of it**: 0.000→0.4333 by supplying
the table; 130/150 gold URIs in prompt; identical LLM/non-LLM outputs under
matched table; 0/21 real-world held-out queries with an incomplete table.

**RQ3 — Does the methodology remain valid on real multilingual RDF?**
**Partially**: metrics and stratification transfer (real one-hop ac1 1.0,
oracle bounds work); cross-graph alignment generalization is not established.

**RQ4 — Actual contributions?** Alignment table = cross-lingual ability;
LLM planning + predicate constraints = in-language accuracy (0.772 vs 0.498;
2-hop ablation 0.933→0.000); localized traversal = cost only (3 orders less
logical access, identical accuracy).

**RQ5 — Is LLM cost justified?** For the *whole* benchmark, a measurable
accuracy gain exists (0.772 vs 0.498 non-LLM matched) at ~8.6 s/query vs
sub-millisecond traversal. For *cross-lingual* queries specifically, the gain
is **zero** when supervision is matched — the seconds of LLM inference buy
nothing over a deterministic linker. Cost justification therefore applies
only to planning-heavy in-language queries.

## Claims requiring revision in the manuscript

1. "Cross-lingual Hits@1 exactly 0.000 when gold absent" → add exact CI
   [0, 0.168].
2. "All Holm-corrected p<1e-7" → correct to p<1e-3 (no_aligner exception).
3. Any framing that LLM *aligns* entities → reframe as LLM *selects from a
   supplied alignment table*.
4. "Outperforms conventional methods" → qualify: outperforms *unsupervised*
   SPARQL/dense; under matched alignment, cross-lingual parity with a
   deterministic linker.
5. "Validated on real RDF" (if present) → replace with methodology transfer
   on real RDF, no cross-graph alignment validation.

## Final decision

- **Scientifically reliable?** The experimental records are reliable and
  reproducible; the *interpretation* in the manuscript needs correction.
- **Baseline comparison fair?** No, as originally framed — unequal alignment
  supervision. Task B provides the corrected comparison.
- **LLM advantage under matched supervision?** Yes, but only for planning on
  in-language queries; **none** for cross-lingual alignment.
- **Real-world validation?** Methodological only; not cross-graph alignment.
- **Ready for Phase 2?** **Yes, conditional on the five claim revisions above.**
  Do not submit before incorporating them; the audit itself is complete.
