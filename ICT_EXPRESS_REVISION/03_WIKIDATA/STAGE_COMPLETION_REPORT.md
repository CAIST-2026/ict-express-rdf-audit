# Stage 4 completion report: Wikidata QID audit and expansion

**Status:** Completed  
**Gate:** Passed with scope limitation recorded.

## Work performed

- Audited the Wikidata QID/PID mechanism and confirmed that multilingual labels are attached to one stable entity URI, not separate graph identities.
- Copied the saved authentic SPARQL responses and derived entity/property files into the revision workspace with SHA-256 hashes.
- Expanded the query set from 55 to 184 queries using only saved triples:
  - 114 one-hop queries from every saved entity–predicate pair;
  - 70 cross-lingual queries covering all 70 entities.
- Executed a deterministic local supervision experiment over all 184 queries under `NO_SUPERVISION`, `MATCHED_SUPERVISION`, and `ORACLE`.
- Computed exact Clopper–Pearson confidence intervals for all aggregate `ac1` values.
- Identified two surface-identical zh/en labels (`Megaupload`, `YouTube`) as the only no-supervision cross-lingual successes, and classified them as lexical overlaps rather than alignment.

## Key results

- one-hop ac1: 1.000 in all three groups (n=114).
- cross-lingual matched ac1: 0.700 overall (49/70, CI [0.579, 0.804]); exactly 1.000 on train-pool entities and 0.000 on 21 held-out entities (CI [0.000, 0.161]).
- oracle cross-lingual ac1: 1.000.

## Scope boundary

The benchmark tests methodology transfer and alignment coverage under a language-partitioned view. It does not test cross-graph entity alignment or the LLM planner on real data. Two-hop/ambiguity/heterogeneous-predicate families remain unexecuted because the saved sample lacks the required chained properties and live WDQS was rate-limited.

## Outputs

- `WIKIDATA_DATASET_REPORT.md`
- `WIKIDATA_ALIGNMENT_POLICY.md`
- `WIKIDATA_REPRODUCIBILITY.md`
- `STAGE_COMPLETION_REPORT.md`
- `queries/WIKIDATA_QUERY_SET.csv`
- `queries/WIKIDATA_GOLD_ANSWERS.csv`
- `results/WIKIDATA_PER_QUERY_RESULTS.csv`
- `results/WIKIDATA_EXPERIMENT_RESULTS.csv`
- `code/build_wikidata_benchmark.py`
- `logs/wikidata_build.log`
