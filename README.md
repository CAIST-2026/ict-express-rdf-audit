# LLM-Guided Bilingual RDF Retrieval: Alignment or Selection?

Public evidence archive for the ICT Express manuscript by Yuxiang Sun and Nan Yin. The latest, corrected six-page manuscript package is in [`final_submission/`](final_submission/), revision **v2.5**. The underlying code and evidence archive remains release **v2.3**. Earlier experiment and audit artifacts remain in the repository as historical records; use `final_submission/` for the current manuscript.

## Current manuscript and package

- [`ICTExpress_Final_Revised.pdf`](final_submission/ICTExpress_Final_Revised.pdf): six-page manuscript.
- [`ICTExpress_Final_Revised.tex`](final_submission/ICTExpress_Final_Revised.tex): LaTeX source.
- [`ICTExpress_Final_Supplementary.zip`](final_submission/ICTExpress_Final_Supplementary.zip): source code, synthetic records, analysis outputs, figures, tables, and the URI-masking pilot records.
- [`ICTExpress_Final_Validation_Report.docx`](final_submission/ICTExpress_Final_Validation_Report.docx): concise revision and evidence-scope record.
- [`reproducibility/README.md`](final_submission/reproducibility/README.md): rebuild instructions and evidence limits.

The v2.5 manuscript removes the requested generative-AI declaration section and includes a metadata check of all 17 references. Bibliographic metadata corrections include a coauthor initial, RDFLib authorship/version, the arXiv survey year, and the full title of a survey article.

## Corrected findings

The application-level prompt reconstruction includes candidate-anchor URIs. The gold URI occurs in **200/200 one-hop prompts (100%)** and **130/150 cross-lingual prompts (86.67%)**. The synthetic result is 386/500 strict successes for the LLM planner and 350/500 for the fixed-$k$ no-aligner baseline; the planner's net gain is concentrated in the cross-lingual family. This is evidence about the evaluated candidate and prompt configuration, not autonomous identity discovery.

A new exploratory intervention on 12 exposed cross-lingual queries yielded rank-1 gold-URI output of **9/12 with full profiles and 1/12 after profile URI lists were emptied**. Anchors, canonical keys, bilingual surface forms, query text, and schema remained available. The result is descriptive and does not isolate all identity cues.

Six paired Wikidata contrasts were recalculated with a single Holm family; none reached adjusted *p* < 0.05. This does not establish equivalence. The No explicit alignment table condition still receives Chinese query text and English candidates. Its 19/21 held-out result is exploratory, and held-out isolation from prompt development is unverified.

## Evidence and reproducibility scope

| Materials | Scope |
|---|---|
| Synthetic generator, saved seeds, primary records/configuration/log, analysis code | Rebuild benchmark records and saved analyses; new model outputs require the Ollama/model environment and may differ. |
| URI-masking pilot CSV and prompt/completion snapshots | Reanalyse the 12 retained paired cases. |
| Three sensitivity result/configuration sets | Reanalyse saved runs; query-text overlaps with the primary sample are 91, 0, and 1, and one run reuses the primary data seed. Run logs are absent. |
| Wikidata rows, configurations, manifest, and two LLM logs | Reanalyse retained outcomes only. The four original query, gold-answer, entity, and attribute inputs listed in the manifest are absent, so a fresh benchmark rerun is not supported. |
| Historical prompts and successful outputs | Not retained. The exact prompt and completion snapshots in this release are for the new URI-masking pilot only. |

The manuscript is an empirical audit of one LLM-guided bilingual RDF retrieval system, not a new retrieval or entity-alignment algorithm. No operator, subscriber, device, or IoT workload was measured. The ICT operations scenarios in the paper motivate the risk of confusing supplied identifiers with entity resolution; they are not measured operational outcomes.

## Rebuild retained analyses

From the repository root:

```sh
python -m pip install -r final_submission/reproducibility/requirements.txt
MPLCONFIGDIR=./final_submission/reproducibility/.mplcache \
XDG_CACHE_HOME=./final_submission/reproducibility/.cache \
MPLBACKEND=Agg python3 final_submission/reproducibility/build_assets.py
```

This rebuilds retained-result tables and figures and reconstructs application-level prompt exposure from source code and saved seeds. It does not reproduce archived model completions byte-for-byte. The URI-masking pilot runner is `final_submission/reproducibility/run_uri_masking_pilot.py`; rerunning it requires Ollama with Qwen2.5-7B and is not expected to guarantee identical completions.

## License

Code and data are released under the MIT License; see [`LICENSE`](LICENSE).
