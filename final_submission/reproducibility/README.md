# Reproducibility supplement

This supplement accompanies *LLM-Guided Bilingual RDF Retrieval: Alignment or Selection?* and is archived in the public repository at https://github.com/CAIST-2026/ict-express-rdf-audit (release v2.8).

## Included material

- `code/`: synthetic benchmark generation, retrieval/evaluation, prompt construction, paired-test utilities, and scripts accompanying retained Wikidata records.
- `data/main/`: the 500-query, seven-variant primary run, configuration and retained experiment log, per-query outcomes, reconstructed prompt-exposure audit, and the historical 12-query URI pilot with exact prompt/completion snapshots.
- `data/seeds/`: three 200-query sensitivity runs and configurations/outcomes. No sensitivity-run logs were retained. Their distinct query-text overlaps with the primary run are 91, 0, and 1; the first sensitivity run reuses the primary data seed.
- `data/wikidata/`: 736 parsed query-level rows, aggregate records, four group configurations, a manifest, and two LLM logs. The four source inputs named in the manifest are absent; these records support reanalysis, not a fresh benchmark rerun.
- `tables/` and `figures/`: manuscript table fragments and generated plots.
- `build_assets.py`: rebuilds retained-result analyses, manuscript tables and figures, and the application-level prompt exposure reconstruction.
- `experiments/v27_uri_intervention/`: stratified 60-query, three-condition URI intervention. Retains all 180 sent prompts/completions, the 40 exact-answer-URI-present/20 exact-answer-URI-absent query manifest, model settings, seeds, query-level outputs, and validation/analysis scripts. Rerunning requires Qwen2.5-7B via Ollama; retained completions support exact reanalysis of the reported run.
- `experiments/v27_mini_ict/`: deterministic synthetic ICT graph probe with 540 triples and 60 bilingual device/alarm/service queries. Includes graph, generation script/seed, mappings, per-query outputs, and domain-scope note; not operator or field data.
- `experiments/v28_ict_qwen/`: Qwen2.5-7B comparison on the same 60 ICT queries against an exact-code parser. Retains all 60 prompts/completions, model settings, seed, query-level outcomes, and validation script. Queries explicitly contain the generated asset code, so this is constrained selection, not semantic entity discovery. Both selectors scored 60/60 under complete mappings and 30/60 after the controlled mapping intervention.
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
| Historical URI-masking pilot | Reanalysis of 12 paired records and inspection of exact saved pilot prompts/completions | Generalization beyond this small sample or autonomous identity-discovery claims |
| New three-condition intervention | Reanalysis of all 180 retained prompts/completions and query-level label/key outcomes; rerunnable with Ollama and Qwen2.5-7B | Autonomous identity discovery: bilingual labels remain candidate-provided in the semantic-only arm |
| Synthetic ICT mini-graph | Exact regeneration of 540 triples, 60 queries, mappings, and deterministic outcomes; retained Qwen trace supports reanalysis and a rerun | Autonomous identity discovery, semantic inference from field language, or operational error rates |
| Sensitivity runs | Reanalysis/rebuilding of three saved 200-query result sets and their overlaps | Independent-seed replication; one run reuses the primary data seed and run logs are absent |
| Wikidata comparison | Reanalysis of 736 parsed rows, configurations, manifest, and two LLM logs | Rerun from original benchmark inputs; the four manifest-listed query, gold-answer, entity, and attribute files are missing |

The synthetic primary output records 49,781 generated triples, 500 queries, Qwen2.5-7B through Ollama, temperature zero, JSON mode, and a 256-token output budget. The archived main log records 500 Ollama-backed full-system planner calls and no mock fallbacks.

The new URI intervention stratifies 60 cross-lingual queries using the 20261120 sample seed: 40 contain the exact answer-bearing URI string and all 20 without that exact string are included; the latter may still contain a counterpart URI or canonical key. Three conditions progressively remove URI values and then canonical keys. All 180 actual prompts and model completions, seeds, and query-level results are retained. The primary outcome is exact normalized selection of the gold opposite-language surface form; exact canonical-key and combined key-or-label identity matches are recorded separately. The validation and analysis scripts check the 180-call trace, the 40/20 sample strata, Ollama backend, URI/key masking, and exact surface/key outcomes. The exact-answer-URI-absent stratum can still contain a counterpart URI or canonical key; it is not identity-cue-free.

The mini ICT probe uses a generated 540-triple bilingual graph and 60 template-based queries. In the complete-mapping condition, both Qwen2.5-7B and an exact-code parser selected all 60 explicit asset codes and retrieved all 60 gold targets and contexts. The paired intervention removes 15 mappings and redirects 15 of 60 mappings, yielding 30/60 exact target retrieval and gold-context retention for each selector. Because every query includes its generated asset code and the model receives a candidate list, this is a constrained-selection and mapping-integrity probe, not semantic identity discovery. The retained prompts/completions, graph, outcomes, script, and seed support reanalysis; rerunning the model requires Ollama and Qwen2.5-7B. This controlled synthetic result is not a field estimate.

The Wikidata `strict_success` field uses a separate evaluator: it requires the top-ranked URI to equal the gold URI and a gold value to occur in the selected entity's evidence. Its `vic` field records gold-value presence in that evidence. This differs from the synthetic answer-text and retrieved-object lexical matching rule. No archived field is a Gwet AC1 statistic.
