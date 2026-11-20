# Reproducibility supplement

This supplement accompanies *LLM-Guided Bilingual RDF Retrieval: Alignment or Selection?* and is archived in the public repository at https://github.com/CAIST-2026/ict-express-rdf-audit (release v2.3).

## Included material

- `code/`: synthetic benchmark generation, retrieval/evaluation, prompt construction, paired-test utilities, and scripts accompanying retained Wikidata records.
- `data/main/`: the 500-query, seven-variant primary run, configuration and retained experiment log, per-query outcomes, reconstructed prompt-exposure audit, and the 12-query URI-masking pilot with exact pilot prompt/completion snapshots.
- `data/seeds/`: three 200-query sensitivity runs and configurations/outcomes. No sensitivity-run logs were retained. Their distinct query-text overlaps with the primary run are 91, 0, and 1; the first sensitivity run reuses the primary data seed.
- `data/wikidata/`: 736 parsed query-level rows, aggregate records, four group configurations, a manifest, and two LLM logs. The four source inputs named in the manifest are absent; these records support reanalysis, not a fresh benchmark rerun.
- `tables/` and `figures/`: manuscript table fragments and generated plots.
- `build_assets.py`: rebuilds retained-result analyses, manuscript tables and figures, and the application-level prompt exposure reconstruction.
- `run_uri_masking_pilot.py`: runs the archived 12-query URI-list redaction intervention; it requires the stated local Ollama model/runtime and may produce different outputs on a new run.
- `traceability.csv`: links manuscript outputs to source records and calculations.

## Rebuild saved analyses

From the package root, install `reproducibility/requirements.txt` and run:

```sh
MPLCONFIGDIR=./reproducibility/.mplcache XDG_CACHE_HOME=./reproducibility/.cache MPLBACKEND=Agg python3 reproducibility/build_assets.py
```

This rebuilds tables and figures from retained query-level records and reconstructs synthetic application-level prompt content from the included code and seeds. The reconstructed complete application-level message includes candidate-anchor URIs: the gold URI occurs in 200/200 one-hop prompts and 130/150 cross-lingual prompts. The application sends one user-role message, with no additional application-level system message or few-shot examples. This is a code-and-configuration reconstruction; historical literal prompt snapshots and successful raw model completions were not retained. The Ollama runtime's internal chat template was not inspected.

The script recalculates the six saved Wikidata paired contrasts from archived outcomes with one Holm family of six tests and rebuilds the primary synthetic ablation family using three planned comparisons. These are analyses of retained outputs, not fresh model runs.

## Evidence scope and limitations

| Material | What the archive supports | What it does not support |
|---|---|---|
| Synthetic primary run | Regeneration of benchmark records from generator and seeds; rebuilding reported analyses and figures from retained outputs; inspection of the retained run log | Guaranteed identical new model responses; the model runtime may vary |
| Prompt exposure | Reconstruction of all application-level prompt fields from code and saved seeds | Inspection of historical literal prompt payloads or the Ollama internal chat template |
| URI-masking pilot | Reanalysis of 12 paired records and inspection of exact saved pilot prompts/completions | Generalization beyond this small sample or autonomous identity-discovery claims |
| Sensitivity runs | Reanalysis/rebuilding of three saved 200-query result sets and their overlaps | Independent-seed replication; one run reuses the primary data seed and run logs are absent |
| Wikidata comparison | Reanalysis of 736 parsed rows, configurations, manifest, and two LLM logs | Rerun from original benchmark inputs; the four manifest-listed query, gold-answer, entity, and attribute files are missing |

The synthetic primary output records 49,781 generated triples, 500 queries, Qwen2.5-7B through Ollama, temperature zero, JSON mode, and a 256-token output budget. The archived main log records 500 Ollama-backed full-system planner calls and no mock fallbacks.

The URI-masking pilot sampled 12 exposed cross-lingual queries with selection seed 20261120. Its redacted condition empties profile URI lists but retains candidate anchors, canonical keys, bilingual surface forms, schema, query, and instructions. In the retained run, rank-1 gold-URI output was 9/12 with full profiles and 1/12 after redaction; exact canonical-key selection was 4/12 and 1/12. Gold URI exposure was 12/12 and 0/12, respectively. These are descriptive pilot counts, not the paper's StrictAcc measure and not an isolation of all identity cues.

The Wikidata `strict_success` field uses a separate evaluator: it requires the top-ranked URI to equal the gold URI and a gold value to occur in the selected entity's evidence. Its `vic` field records gold-value presence in that evidence. This differs from the synthetic answer-text and retrieved-object lexical matching rule. No archived field is a Gwet AC1 statistic.
