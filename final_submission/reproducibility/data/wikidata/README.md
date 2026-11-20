# Archived Wikidata comparison records

This folder contains retained query-level outputs for the matched LLM, No explicit alignment table condition, deterministic comparison, and oracle groups. The records support reanalysis of saved outcomes; missing source inputs prevent a fresh benchmark rerun. This archive is available in the public repository at https://github.com/CAIST-2026/ict-express-rdf-audit (release v2.3).

## Included records

- `query_level_results.csv`: 736 rows, exactly 184 unique queries for each of four groups.
- `raw_*.csv`: parsed group outputs.
- `aggregate_metrics.csv` and `statistical_tests.csv`: recomputed summaries and six paired contrasts with a single Holm correction family.
- `configs/`: four retained run configurations.
- `logs/`: logs for the two LLM conditions only; no deterministic run log was retained.
- `dataset_manifest.json`: checksums and sizes recorded for four original input files. The query set, gold-answer file, entity data, and attribute data listed in the manifest are not included.

## Interpretation and limits

The No explicit alignment table condition omits the explicit training-pool alignment map from the LLM prompt. It still receives Chinese query text and English candidate labels, so it retains cross-language information. The 19/21 held-out result for this condition is exploratory; saved artifacts do not establish isolation from prompt development or manual inspection. Historical prompt snapshots and successful raw completions are absent. The manifest documents the missing source files but does not make them available, so the archived results cannot be independently regenerated from the original queries and graph inputs.

`strict_success` is the archived Wikidata evaluator's binary outcome: the predicted URI equals the gold URI and at least one gold value occurs in the selected entity's evidence. `vic` denotes that evidence-value condition alone. This is separate from the synthetic benchmark's answer-text and retrieved-object lexical matching rule. Neither field is Gwet's AC1 coefficient.
