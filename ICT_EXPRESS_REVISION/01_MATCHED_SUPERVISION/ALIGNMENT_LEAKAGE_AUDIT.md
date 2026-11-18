# Alignment Leakage Audit — Matched Supervision

Date: 2026-11-18. Scope: synthetic benchmark and Phase 1 matched-supervision
experiment. Serialised lookup snapshot:
`data/alignment_snapshot.json` (seed 20260101, memory seed 20260104,
coverage 0.92).

## 1. What the controlled groups actually receive

| Group | Query text | Surface anchors | Shared alignment table | Gold URIs | Predicate constraints |
|---|---|---|---|---|---|
| NO_SUPERVISION | yes | yes | **no** | no | query-side `infer_predicate_constraints` |
| MATCHED_SUPERVISION | yes | yes | **yes — same table as planner** | no | query-side `infer_predicate_constraints` |
| ORACLE | yes | yes | no need | **yes (upper bound only)** | query-side `infer_predicate_constraints` |
| LLM planner (`full_system`) | yes | yes | **yes, via prompt profiles** | no (except when the table covers it) | LLM-emitted + query-side fallback |

The LLM prompt is built from `knowledge[key] → label_to_key → alias_index`,
the same deterministic path serialised in `alignment_snapshot.json` and given
to the non-LLM MATCHED group. `aligned_uris` in the saved result CSV is a
**planner output**, not a prompt input.

## 2. Required leakage checks

1. **Gold URI in LLM prompt?** Yes for 130/150 (86.7%) cross-lingual queries.
   This is the original confound. It is measured by `alignment_probe.py` and
   reported in the paper; it is not hidden. For the remaining 20 queries,
   observed Hits@1 is 0/20 with exact 95% CI [0, 0.168].
2. **Alignment table contains test answers?** The truth-derived table can
   contain a query's gold counterpart by construction (coverage 0.92). Under
   MATCHED_SUPERVISION this information is deliberately given to both LLM and
   non-LLM systems. It is therefore *supervision*, not autonomous alignment.
3. **Candidate generation uses test-set entities?** `CandidateAnchorMapper`
   uses the query text against a global label/alias index built from the fixed
   generator. No query-specific test gold mapping is injected. The aligned URI
   list is derived from anchors through the shared table.
4. **Query rewriting uses test mappings?** No query rewriting stage exists;
   predicate constraints come from `infer_predicate_constraints(query.text)`.
5. **Oracle misuse?** ORACLE receives gold URIs and reaches ac1 = 1.000. It is
   labelled an upper bound in code, CSV, and manuscript; it is not a baseline.
6. **Same external supervision?** For the aligned URI set, yes. The LLM also
   receives natural-language entity profiles and emits its own plan; the
   non-LLM linker uses the shared table and query-side predicate constraints.
   Therefore the *alignment information* is matched, but the *planner
   machinery* is not, which is exactly the intended contrast.

## 3. Serialised snapshot

`data/alignment_snapshot.json` contains:
- `knowledge`: canonical key → recalled surface forms;
- `label_to_key`: normalised surface form → canonical key;
- `alias_index`: normalised surface form → list of `[uri, graph]`;
- `uri_graph`: URI → graph name.

This closes the inventory gap identified in Stage 1.

## 4. Audit verdict

No undisclosed test-gold leakage was found in MATCHED or NO_SUPERVISION.
The original cross-lingual advantage is explained by unequal access to the
alignment table. ORACLE is correctly isolated. The remaining confound is not
leakage but a scope difference: LLM and non-LLM planners differ in predicate
selection and profile conditioning; predicate-level labels are not saved and
cannot be audited retrospectively.
