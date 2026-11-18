# ICT Express Revision — Reproduction Package

This directory contains the revised study, all new experiment code, results,
and the compiled manuscript. Input materials under `/Users/yuxiangsun/Desktop/ICT/`
(original `manuscript/`, `rdf_llm_ea/`, `audit/`, `elsarticle/`) were **never
modified**; everything new lives here.

## 1. What changed and why (one paragraph)

The original evaluation coupled the answer generator with the judge (near-tautological
success), used a "SPARQL" baseline that never executed SPARQL, used a monolingual
encoder for the "vector" baseline, hid an 11% JSON-truncation fallback, and mixed
latency protocols. This revision adds: a judge-free evidence-constrained metric
(`ac1`, `vic`), an **alignment-supervision probe** (the paper's central
methodological result), capability-corrected baselines (real SPARQL 1.1 via
rdflib, multilingual dense retrieval via e5-small, transliteration linker),
a three-protocol latency study, and a single-protocol scaling sweep.

## 2. Environment

- macOS arm64, Python 3.13 (`env/venv/`), torch 2.11.0 (MPS), transformers
  4.46.3, rdflib 7.6.0, pandas, numpy, scipy, matplotlib, pypinyin.
- `experiments/vendor_install.py` is a pip replacement used to vendor wheels
  without temp files; the resulting venv is committed to `env/venv/`.
- LLM: Ollama 0.9.6 serving `qwen2.5:7b` (Q4_K_M) at `http://localhost:11434`.
- Dense encoder pinned to the local snapshot
  `intfloat/multilingual-e5-small` (commit `614241f6...`), path configurable
  via `E5_MODEL_PATH`.

## 3. One-command reproduction

```bash
# 0) start the model server
ollama serve   # separate terminal

# 1) main results (reused, do not re-run): rdf_llm_ea/outputs_audit/
#    regenerated with:
#    cd ../rdf_llm_ea && python run_audit_experiment.py --coverage 0.92 --num-predict 256

# 2) fair baselines (~4 min on MPS)
env/venv/bin/python experiments/baselines_ict.py \
    --out results/baselines/seed_20260101 \
    --systems sparql_real,translit,dense,dense_ne

# 3) alignment-supervision probe (<1 min, no model calls)
env/venv/bin/python experiments/alignment_probe.py \
    --results ../rdf_llm_ea/outputs_audit/experimental_results.csv \
    --out results/main/alignment_probe

# 4) paired statistics (<1 min)
env/venv/bin/python experiments/stats_ict.py \
    --main ../rdf_llm_ea/outputs_audit/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/stats

# 5) latency protocols (~15 min; needs Ollama)
env/venv/bin/python experiments/latency_ict.py --n 24 --out results/latency

# 6) scaling sweep (~40 min; needs Ollama)
env/venv/bin/python experiments/scaling_ict.py \
    --sizes 10000 50000 100000 200000 --llm-n 8 --fast-n 100 --out results/scaling

# 7) transliteration diagnosis (<1 min)
env/venv/bin/python experiments/translit_diagnosis.py \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/diagnostics

# 8) tables + figures + traceability
env/venv/bin/python experiments/summarize.py \
    --main ../rdf_llm_ea/outputs_audit/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --probe results/main/alignment_probe/probe_by_group.csv \
    --latency results/latency/protocol_summary.csv \
    --scaling results/scaling/scaling.csv \
    --stats results/stats --out .

# 9) manuscript
cd paper && pdflatex main.tex && pdflatex main.tex
```

All scripts write `run_config.json` (exact args + env) and per-query CSVs
next to their outputs. Seeds are fixed (`20260101` data, `+1` benchmark,
`+3` memory) so every run is deterministic given the same model and machine.

## 4. Results layout

```
results/
  main/alignment_probe/     probe_by_group.csv, probe_per_query.csv, config
  baselines/seed_20260101/  per_query.csv, aggregate.csv, per_category.csv, run_config.json
  stats/                    descriptive.csv, pairwise_tests.csv, stats_config.json
  latency/                  per_query.csv, protocol_summary.csv, run_config.json
  scaling/                  scaling.csv, gsr_fit.csv, run_config.json
  diagnostics/              translit_by_name_length.csv, translit_per_query.csv
tables/                     *.tex + *.csv (script-generated, \input from the paper)
figures/                    fig2_accuracy, fig3_probe, fig5_latency (+fig4 scaling) PDFs
paper/main.tex + main.pdf   cas-dc (Elsevier CAS), 4 pages, compiles clean
traceability.csv            paper item -> file/columns/script
```

## 5. Headline numbers (see traceability.csv for provenance)

| system | ac1 | 1-hop | 2-hop | cross-ling. | serial ms |
|---|---|---|---|---|---|
| Localized (full) | 0.772 | 0.905 | 0.933 | 0.433 | 6703 |
| SPARQL 1.1 (rdflib) | 0.646 | 0.940 | 0.900 | 0.000 | 271 |
| Dense e5 + traversal | 0.544 | 0.925 | 0.580 | 0.000 | 16 |
| Transliteration | 0.532 | 0.640 | 0.613 | 0.307 | 0.08 |

Probe: 86.7% of cross-lingual gold URIs are in the prompt; Hits@1 = 0.500
(present) vs 0.000 (absent). Transliteration: perfect on the 46
two-character (romanisation-paired) names, zero on the 104 three-character
names.

## 6. Known limitations (honest list)

- **Synthetic data only.** No real ICT/telecom deployment or data; the
  benchmark tests whether an alignment table was *provided*, not whether a
  system can *infer* alignment.
- **Simulated LLM memory** (coverage 0.92) is an input parameter that bounds
  cross-lingual performance; not a measured model property.
- **One model, one machine**: qwen2.5:7b on local Ollama; latency numbers do
  not transfer to hosted APIs.
- **No independent human annotation**; `ac1`/`vic` are string-match checks.
- **sentence-transformers unavailable** in the sandbox; e5-small is reproduced
  with transformers mean pooling (documented in `dense_baseline.py`); output
  equivalence spot-checked.
- **GSR** is a logical access ratio, not measured I/O or memory.
- Scaling sweep uses `--llm-n 8` per size (LLM latency is size-independent in
  this design; the size claim rests on GSR/accuracy, non-LLM variants use
  `--fast-n 100`).

## 7. What the authors still need to confirm before submission

1. ~~Author names / affiliations~~ **Done**: Yuxiang Sun (Guangzhou
   University of Software, Guangzhou, China, corresponding; ORCID
   0000-0003-0165-7664) and Nan Yin (Canada Advanced Institute of Science
   and Technology, Ottawa, Canada; ORCID 0009-0007-3506-9592). ORCIDs are
   printed in the title-page footnote.
2. CRediT roles are currently distributed 1-to-1 (Sun: conceptualization/
   software/writing; Yin: validation/curating/editing) — confirm this
   reflects the actual division of labour.
3. The generative-AI declaration wording (current text is the journal's
   template adapted; authors must confirm actual usage).
4. Reference list: `barnett2024seven` DOI and page numbers were written from
   memory — **must be verified against the publisher page** before submission;
   same for the rdflib/e5/qwen2.5 citations (arXiv IDs and version).
5. Whether to keep the legacy baselines in Table 1 (currently kept for
   transparency; could be moved to an appendix).
6. ICT Express submission portal requires the declarations tool output for
   competing interests — generate it at submission time.
7. **Public release commitment.** The paper now states that the benchmark
   generator, seeds, queries, probe, baselines, statistics scripts, and
   per-query records will be released under an open licence upon
   publication, with the repository URL and archival DOI added at submission
   time. The authors must actually create that public repository at (or
   before) submission — this package is submission-ready as the starting
   point; the release statement must not remain a promise.
