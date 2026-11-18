# Reproducibility Checklist — Task A

Date: 2026-11-18

This checklist states, item by item, whether each element of the original
experiment can be reproduced from the preserved records and code.

## 1. Artifacts preserved (never modified)

- `manuscript/` — original 23-page Springer manuscript
- `rdf_llm_ea/` — original code, benchmark generator, all `outputs_*` directories
- `audit/` — phase-1/2 audit records
- `ict_express_submission/` — revised package (also published at
  https://github.com/CAIST-2026/ict-express-rdf-audit)
- Original raw results were **not** overwritten; the revised package contains
  copies (`upstream_results/`) plus new per-query records.

## 2. Reproducibility matrix

| Item | Reproducible? | Command / evidence |
|---|---|---|
| RDF store (49,781 triples) | ✅ Exact | `build_dataset(50_000, seed=20260101)` → 49,781 triples, verified in `results/triple_integrity.json` |
| 500-query benchmark | ✅ | Deterministic from `scalable_benchmark.py`; 200/150/150 category split reproduced in records |
| Gold values / URIs | ✅ | 500/500 gold values found in regenerated graph |
| Alignment table (coverage 0.92) | ✅ | `build_llm_memory(bundle, 0.92, seed=20260103)`; probe reproduced 130 exposed / 20 absent |
| Metric computation (hits1/mrr/ac1/vic/GSR) | ✅ | `audit/audit_recompute.py` recomputes all reported values from saved CSVs |
| Main LLM run (7 variants) | ⚠️ Not re-executed | Ollama + qwen2.5:7b available; re-running changes latency values and LLM sampling may vary. Original records trusted (0 fallbacks, internally consistent). Command: `cd rdf_llm_ea && python run_audit_experiment.py --coverage 0.92 --num-predict 256` |
| Fair baselines (SPARQL/dense/translit) | ✅ in principle | `experiments/baselines_ict.py`; dense encoder needs `torch`+`transformers` and model weights (see §3) |
| Statistical tests | ✅ | Recomputed in Task D from saved per-query records |
| Figures / tables | ✅ | `experiments/summarize.py` regenerates all tables/figures from CSVs |

## 3. Environment status at audit time

- Python 3.13.12 venv at `ICT_EXPRESS_PHASE1/env/` — installed via
  `env/vendor_install.py` (wheel download + unzip, no pip temp dir needed).
- Installed: rdflib 7.6.0, numpy 2.5.5, pandas 3.1.1, scipy 1.18.1, pypinyin 0.55.0.
- Ollama 0.9.6 running at localhost:11434 with qwen2.5:7b (verified).
- **Not installed in the fresh Phase-1 env**: torch, transformers. The dense
  baseline therefore cannot be re-executed here unless these are installed and
  the `multilingual-e5-small` weights are downloaded. This does **not** affect
  Tasks A/D (record-based) or the non-dense parts of Task B.
- Note: the original main run used Python 3.11.5 / rdflib 7.5.0 / pandas 3.0.6
  / torch 2.14.0 (see `run_config.json`). The Phase-1 env uses slightly newer
  versions; deterministic graph regeneration is unaffected (verified).

## 4. Seeds and fixed parameters

| Parameter | Value | Source |
|---|---|---|
| Data / run seed | 20260101 | `run_config.json`, `scalable_data.SEED` |
| Benchmark offset | +1 | `scalable_benchmark` |
| LLM memory seed | +3 (20260103) | `build_llm_memory` call |
| Memory coverage | 0.92 | `run_config.json` |
| LLM | qwen2.5:7b, temp 0, JSON, num_predict 256 | `run_config.json` |
| Query count | 500 | records |

## 5. Known gaps

1. Original runs did not log **prompt payloads verbatim**; alignment exposure
   was reconstructed deterministically from seeds (`alignment_probe.py`).
2. Original runs did not log **evidence triple URIs verbatim**; `vic` and
   context counts are internally consistent but not triple-ID-auditable.
3. The judge-proxy metrics in the original run (`faithfulness_llm`, etc.) are
   not used anywhere in the revised paper; `ac1`/`vic` are deterministic.
4. Latency from the 500-query 4-worker run (mean ~27.9 s, LLM-dominated) must
   not be compared with the 24-query serial protocol (mean 6.7 s); the paper
   separates them.
