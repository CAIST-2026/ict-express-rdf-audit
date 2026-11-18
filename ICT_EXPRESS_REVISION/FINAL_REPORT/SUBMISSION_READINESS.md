# SUBMISSION_READINESS

## Final judgment

**Ready after Minor Revision**

The manuscript is not in the “Ready for Submission” category because two structural limitations remain visible to a strict reviewer: (i) the main benchmark is synthetic, and (ii) the Wikidata check does not validate cross-graph entity alignment. Both are disclosed, but they constrain how the contribution can be framed. It is not “Not Ready” because all P0 defects identified during the audit have been corrected with executed experiments and traceable artefacts.

## Conditions before submission

1. Keep the paper framed as an evidence-constrained audit/measurement letter.
2. Do not add claims of real ICT deployment or real cross-graph alignment.
3. Preserve the “0/20 observed, exact CI [0, 0.168]” wording.
4. Preserve the Holm-corrected p-value wording.
5. Preserve the unified-workload latency table and dense-e5 exclusion note.
6. Obtain a final native-English language pass if available.

## Strong points

- All headline numbers trace to saved per-query results.
- Matched supervision directly tests the central attribution question.
- Real SPARQL executes SPARQL 1.1.
- Multilingual dense retrieval replaces the monolingual baseline.
- Latency now uses one workload for all executable systems.
- Statistics use paired tests, exact intervals, Holm correction, and effect sizes.
- GitHub release is tagged and the manuscript points to a verified commit.

## Residual risks

- One model, one machine, synthetic main benchmark.
- 20-query unexposed stratum remains small.
- Dense e5 latency unavailable in the unified environment.
- No two-hop/ambiguity families in the real Wikidata check.
- Simplified non-LLM two-hop ranker may understate a fully tuned system.

## Final artefacts

- `FINAL_MANUSCRIPT/main.tex`
- `FINAL_MANUSCRIPT/main.pdf` (6 pages)
- `FINAL_TABLES_AND_FIGURES/`
- `FINAL_EXPERIMENT_REPORT.md`
- `FINAL_REVISION_REPORT.md`
- `FINAL_REVIEWER_SIMULATION.md`
- `CONSISTENCY_CHECK.csv` (21/21 PASS)
