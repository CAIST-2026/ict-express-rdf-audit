# LLM-Guided Bilingual RDF Retrieval: Alignment or Selection?

Public evidence archive for the ICT Express manuscript by Yuxiang Sun and Nan Yin. The current manuscript package is revision **v2.8** in [`final_submission/`](final_submission/); earlier tagged revisions remain available as historical records.

## Current package

- [`ICTExpress_Revised_Manuscript.pdf`](final_submission/ICTExpress_Revised_Manuscript.pdf): six-page revised manuscript.
- [`ICTExpress_Revised_Manuscript.tex`](final_submission/ICTExpress_Revised_Manuscript.tex): LaTeX source.
- [`ICTExpress_Revised_Supplementary.zip`](final_submission/ICTExpress_Revised_Supplementary.zip): scripts, synthetic data, retained analyses, prompts, completions, and run documentation.
- [`ICTExpress_Revision_Log.docx`](final_submission/ICTExpress_Revision_Log.docx): concise revision and validation record.
- [`reproducibility/README.md`](final_submission/reproducibility/README.md): rebuild instructions and evidence limits.

## Findings and scope

The complete application-level prompt reconstruction includes candidate-anchor URIs. The exact answer-bearing URI occurs in **200/200 one-hop prompts** and **130/150 cross-lingual prompts**. The planner recorded 386/500 strict successes versus 350/500 for the fixed-$k$ no-aligner baseline; its net gain was confined to the cross-lingual family. These results characterize one truth-profiled pipeline and do not establish autonomous entity discovery.

A three-condition URI intervention used 60 stratified cross-lingual queries: 40 prompts contained the exact answer-bearing URI and 20 did not. The latter could still contain a counterpart URI or canonical key. Exact opposite-language label matches across full, URI-redacted, and semantic-only prompts were **36/40, 32/40, and 31/40** in the first stratum and **1/20, 0/20, and 0/20** in the second. The semantic-only condition retained truth-derived bilingual candidate labels, so it measures selection among supplied candidates. All 180 prompts and model completions are archived.

The synthetic ICT mini-graph contains 540 triples and 60 device, alarm, and service queries. Qwen2.5-7B and an exact-code parser both selected all 60 exposed asset codes. With complete mappings, both retrieved 60/60 targets and contexts; after 15 mappings were removed and 15 redirected, both retained 30/60 correct targets and contexts. This is an identifier-conditioned synthetic probe, not field data or an estimate of operational error rates. Prompts, completions, settings, seeds, and outcomes are retained.

Six archived Wikidata paired contrasts were non-significant after Holm correction. The held-out 19/21 result remains exploratory. Four Wikidata source inputs and successful historical prompts/completions are absent; those records support reanalysis, not a fresh benchmark run. Historical sensitivity runs are descriptive, with query overlaps 91, 0, and 1; one reuses the primary data seed.

The manuscript is an empirical audit of one LLM-guided bilingual RDF retrieval system, not a new retrieval or entity-alignment algorithm. No operator, subscriber, device, or IoT workload was measured.

## Rebuild retained analyses

From the repository root:

```sh
python -m pip install -r final_submission/reproducibility/requirements.txt
MPLCONFIGDIR=./final_submission/reproducibility/.mplcache \
XDG_CACHE_HOME=./final_submission/reproducibility/.cache \
MPLBACKEND=Agg python3 final_submission/reproducibility/build_assets.py
```

The URI intervention and ICT Qwen comparison can be rerun with Ollama and Qwen2.5-7B; generated completions may vary across environments. The synthetic ICT graph and deterministic mapping outcomes are reproducible from the retained generator and seed. Archived Wikidata outputs support reanalysis only because the original source inputs are missing. Code and data use the MIT License; see [`LICENSE`](LICENSE).
