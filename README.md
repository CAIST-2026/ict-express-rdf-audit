# Evidence-Constrained Audit of LLM-Guided Retrieval over Heterogeneous Bilingual RDF Graphs

Reproduction package for the ICT Express letter *"What Does the LLM Actually
Contribute?"* by Yuxiang Sun and Nan Yin.

## What this repository contains

| Path | Contents |
|---|---|
| `experiments/` | All experiment scripts (probe, fair baselines, statistics, latency, scaling, diagnosis, figure/table generation) |
| `upstream/` | Six core modules from the original `rdf_llm_ea` codebase, bundled so the package is self-contained |
| `results/` | Per-query result CSVs and run configs for every experiment (500 queries × multiple systems) |
| `tables/`, `figures/` | Script-generated LaTeX tables and PDF figures |
| `paper/main.tex`, `paper/main.pdf` | Manuscript source and compiled PDF (Elsevier `cas-dc`, 6 pages) |
| `ICT_EXPRESS_PHASE1/` | Phase 1 audit: matched-supervision experiment, real Wikidata transfer check, exact statistics, reports, and publication-ready tables |
| `docs/` | Positioning memo and final verification report |
| `traceability.csv` | Maps every number in the paper to its source file, columns, and generating script |

The main benchmark is **fully synthetic** — no real operator, subscriber, or
device data is included. `ICT_EXPRESS_PHASE1/real_world_benchmark/` contains a
small transfer check built from authentic, CC0 Wikidata RDF labels; it does not
contain operator, subscriber, or device data and does not validate cross-graph
entity alignment.

## Quick start

```bash
# 1. Install dependencies (Python >= 3.11)
python -m venv env && source env/bin/activate
pip install -r requirements.txt

# 2. Start the LLM server (needed for main/ablation/latency/scaling runs)
ollama pull qwen2.5:7b
ollama serve

# 3. Run experiments (paths are portable — no absolute paths required)
python experiments/baselines_ict.py --out results/baselines/seed_20260101 \
    --systems sparql_real,translit,dense,dense_ne
python experiments/alignment_probe.py \
    --results upstream_results/experimental_results.csv \
    --out results/main/alignment_probe
python experiments/stats_ict.py \
    --main upstream_results/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/stats
python experiments/latency_ict.py --n 24 --out results/latency
python experiments/scaling_ict.py \
    --sizes 10000 50000 100000 200000 --llm-n 8 --fast-n 100 --out results/scaling
python experiments/translit_diagnosis.py \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --out results/diagnostics

# 4. Regenerate tables, figures, and traceability
python experiments/summarize.py \
    --main upstream_results/experimental_results.csv \
    --baselines results/baselines/seed_20260101/per_query.csv \
    --probe results/main/alignment_probe/probe_by_group.csv \
    --latency results/latency/protocol_summary.csv \
    --scaling results/scaling/scaling.csv \
    --stats results/stats --out .
```

# 5. Phase 1 audit (matched supervision, stats, publication tables; no LLM server)
python ICT_EXPRESS_PHASE1/audit/audit_recompute.py > ICT_EXPRESS_PHASE1/results/audit_recompute.json
python ICT_EXPRESS_PHASE1/audit/verify_triples.py
python ICT_EXPRESS_PHASE1/baseline_fairness/matched_supervision.py
python ICT_EXPRESS_PHASE1/baseline_fairness/build_comparison.py
python ICT_EXPRESS_PHASE1/statistical_verification/stats_verify.py
python ICT_EXPRESS_PHASE1/reports/generate_tables.py
# real-Wikidata offline check: python ICT_EXPRESS_PHASE1/real_world_benchmark/RUN_LOCAL_EXPERIMENT.py
```

**Note on `upstream_results/`:** the reused main run (500 queries × 7 variants)
from the original study is included under `upstream_results/` so the probe,
statistics, and summarisation steps work out of the box. Set the environment
variable `RDF_LLM_EA_SRC` to point at an alternative source tree if needed;
otherwise the bundled `upstream/` directory is used.

Seeds are fixed (`20260101` data, `+1` benchmark, `+3` memory) so results are
deterministic given the same model and machine. Every script writes a
`run_config.json` with exact arguments and per-query CSVs.

## Headline results

| System | ac1 | 1-hop | 2-hop | cross-ling. |
|---|---|---|---|---|
| Localized (full) | 0.772 | 0.905 | 0.933 | 0.433 |
| SPARQL 1.1 (rdflib) | 0.646 | 0.940 | 0.900 | 0.000 |
| Dense e5 + traversal | 0.544 | 0.925 | 0.580 | 0.000 |
| Transliteration | 0.532 | 0.640 | 0.613 | 0.307 |

Central finding: on 86.7% of cross-lingual queries the gold URI is already in
the LLM planner's prompt; Hits@1 is 0.500 when present and 0/20 observed when
absent (exact 95% CI [0, 0.168]). Under matched supervision a deterministic
linker attains exactly the same cross-lingual ac1 as the 7B planner (0.433;
0/150 discordant pairs), so the original cross-lingual advantage came from
unequal supervision. The LLM's overall lead (0.772 vs.\ 0.498) is confined to
planning and predicate selection. See `ICT_EXPRESS_PHASE1/` for the matched,
real-RDF, and exact-CI evidence.

## Environment notes

- Tested on macOS arm64, Python 3.13, torch 2.11 (MPS), transformers 4.46.3,
  rdflib 7.6.0, pandas 3.1.1, numpy 2.5.4, scipy 1.18.1.
- LLM: Ollama serving `qwen2.5:7b` (Q4_K_M) at `http://localhost:11434`.
- Dense encoder: `intfloat/multilingual-e5-small` (auto-downloaded or set
  `E5_MODEL_PATH`).
- `sentence-transformers` was unavailable in the original sandbox; the dense
  baseline uses `transformers` mean pooling with documented equivalence.

## Citation

See `paper/main.tex` for the author list, affiliations, and funding
(2026 Research Project of Guangzhou University of Software, KY202649).

## Licence

Code and data are released under the MIT License (see `LICENSE`).
