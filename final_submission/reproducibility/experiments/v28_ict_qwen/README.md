# Qwen ICT candidate-selection probe

This probe runs Qwen2.5-7B once on each of the same 60 queries in the synthetic mini ICT graph. For each query, the model receives 20 bilingual candidates in the relevant domain and must select a source asset code. Each generated query includes that code, so this tests constrained candidate selection and response behavior, not autonomous cross-lingual inference. A deterministic exact-code parser is the baseline. The selected code is passed through complete and missing/stale mappings, with target retrieval and gold-context retention scored from the RDF graph.

The model selected all 60 codes correctly, matching the deterministic parser. Both selectors retrieved 60/60 targets and contexts with complete mappings and 30/60 under the mapping intervention. All 60 prompts and completions, seeds, model settings, timings, and query-level outcomes are retained. The graph and queries are synthetic, not operator data, and do not estimate field performance.

Run `python3 run_ict_qwen_probe.py` with Ollama and `qwen2.5:7b` available. Run `python3 validate_ict_qwen.py` to check the retained trace and outcomes.
