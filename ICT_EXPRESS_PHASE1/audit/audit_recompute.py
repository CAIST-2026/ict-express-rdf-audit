"""Task A — recompute every manuscript-reported number from saved raw records.

Reads ONLY original/saved records; never modifies them.
Outputs a JSON audit object to stdout for inclusion in the audit report.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

SUB = Path(__file__).resolve().parents[2]
MAIN = SUB / "upstream_results" / "experimental_results.csv"
BASE = SUB / "results" / "baselines" / "seed_20260101" / "per_query.csv"
PROBE = SUB / "results" / "main" / "alignment_probe" / "probe_by_group.csv"
CFG = SUB / "upstream_results" / "run_config.json"

def norm_main(d: pd.DataFrame) -> pd.DataFrame:
    d = d.rename(columns={"success_strict": "ac1", "evidence_grounded": "vic",
                          "context_triples": "ctx_triples", "variant": "system"})
    return d

def r(x, n=4):
    return None if x is None or (isinstance(x, float) and pd.isna(x)) else round(float(x), n)

def main():
    out: dict = {"source_files": {str(p.relative_to(SUB)): p.stat().st_size
                                  for p in (MAIN, BASE, PROBE, CFG)}}
    cfg = json.loads(CFG.read_text())
    m = norm_main(pd.read_csv(MAIN))
    b = pd.read_csv(BASE)
    p = pd.read_csv(PROBE)

    # ---- store / query counts from config and records ----
    out["store"] = {
        "triples_reported": 49781, "triples_config": cfg.get("store_triples"),
        "entities_reported": 3481, "entities_config": cfg.get("entities"),
        "ga_triples": cfg.get("graph_a_triples"), "gb_triples": cfg.get("graph_b_triples"),
        "sum_ga_gb": (cfg.get("graph_a_triples") or 0) + (cfg.get("graph_b_triples") or 0),
    }
    out["queries"] = {
        "n_reported": 500,
        "n_main_unique": int(m.qid.nunique()),
        "n_main_rows": int(len(m)),
        "variants": sorted(m.system.unique().tolist()),
        "per_variant_rows": m.groupby("system").size().to_dict(),
        "categories": m[m.system == "full_system"].category.value_counts().to_dict(),
        "baseline_unique_qids": int(b.qid.nunique()),
        "baseline_systems": sorted(b.system.unique().tolist()),
        "baseline_rows": int(len(b)),
    }

    # ---- main system metrics (recomputed from per-query rows) ----
    systems = {}
    for system, d in m.groupby("system"):
        systems[system] = {"hits1": r(d.hits1.mean()), "mrr": r(d.mrr.mean()),
                           "ac1": r(d.ac1.mean()), "vic": r(d.vic.mean()),
                           "gsr": r(d.gsr.mean(), 6)}
    for system, d in b.groupby("system"):
        systems[system] = {"hits1": r(d.hits1.mean()), "mrr": r(d.mrr.mean()),
                           "ac1": r(d.ac1.mean()), "vic": r(d.vic.mean()),
                           "gsr": r(d.gsr.mean(), 6)}
    out["system_metrics_recomputed"] = systems

    reported = {"full_system": {"hits1": .808, "ac1": .772, "vic": .894},
                "sparql_real": {"hits1": .646, "ac1": .646, "vic": .700},
                "dense": {"hits1": .544, "ac1": .544, "vic": .672},
                "translit": {"hits1": .532, "ac1": .532, "vic": .792}}
    out["reported_vs_recomputed"] = {
        s: {k: {"reported": v, "recomputed": systems.get(s, {}).get(k),
                "match": systems.get(s, {}).get(k) == v}
            for k, v in d.items()} for s, d in reported.items()}

    # ---- per-category ac1 ----
    cat = {}
    for system in ("full_system", "sparql_real", "dense", "translit"):
        d = m[m.system == system] if system in set(m.system) else b[b.system == system]
        cat[system] = d.groupby("category").ac1.mean().round(4).to_dict()
    out["ac1_by_category"] = cat

    # ---- probe: exposure rate and conditional Hits@1 ----
    cross = p[p.category == "cross-lingual"].set_index("group")
    out["probe"] = {
        "cross_rows": p[p.category == "cross-lingual"] .to_dict("records"),
        "n_exposed": int(cross.loc["gold_in_prompt", "n"]) if "gold_in_prompt" in cross.index else None,
        "n_unexposed": int(cross.loc["gold_absent", "n"]) if "gold_absent" in cross.index else None,
        "exposed_rate": round(cross.loc["gold_in_prompt", "n"] /
                              (cross.loc["gold_in_prompt", "n"] + cross.loc["gold_absent", "n"]), 4)
                        if "gold_in_prompt" in cross.index and "gold_absent" in cross.index else None,
        "hits1_exposed": r(cross.loc["gold_in_prompt", "hits1"]) if "gold_in_prompt" in cross.index else None,
        "hits1_unexposed": r(cross.loc["gold_absent", "hits1"]) if "gold_absent" in cross.index else None,
    }

    # ---- alignment table construction: gold URIs in aligned_uris field ----
    fs = m[m.system == "full_system"].copy()
    def gold_in_aligned(row):
        if pd.isna(row.get("aligned_uris")) or not str(row.get("aligned_uris")):
            return None
        return str(row.gt_values)  # retained for manual inspection; annotated below
    out["alignment_field"] = {
        "full_system_rows_with_aligned_uris": int(fs.aligned_uris.notna().sum()),
        "example_aligned_uris": fs.aligned_uris.dropna().head(3).tolist(),
        "note": "aligned_uris is the planner OUTPUT, not the prompt input. "
                "Prompt input is reconstructed by alignment_probe.py from seeds.",
    }

    # ---- gold URI / evidence correctness (structural checks) ----
    out["structural_checks"] = {
        "full_system_gt_values_nonempty": int(fs.gt_values.notna().sum()),
        "full_system_hits1_binary_valid": bool(set(fs.hits1.unique()) <= {0.0, 1.0}),
        "full_system_ac1_binary_valid": bool(set(fs.ac1.unique()) <= {0.0, 1.0}),
        "full_system_vic_binary_valid": bool(set(fs.vic.unique()) <= {0.0, 1.0}),
        "ac1_implies_vic": bool(((fs.ac1 > fs.vic) & fs.ac1.notna() & fs.vic.notna()).sum() == 0),
        "gsr_in_unit_interval_full": bool(fs.gsr.between(0, 1).all()),
        "gsr_in_unit_interval_baselines": bool(b.gsr.between(0, 1).all()),
        "triples_scanned_nonnegative": bool((fs.triples_scanned >= 0).all()),
        "fallback_count": int((fs.failure_mode != "ok").sum()),
        "backend_counts": fs.backend.value_counts().to_dict(),
    }

    # ---- provenance of timing fields ----
    out["timing"] = {
        "fields": ["t_surface_ms", "t_llm_ms", "t_traversal_ms", "t_total_ms"],
        "full_system_mean_llm_ms": r(fs.t_llm_ms.mean(), 2),
        "full_system_mean_total_ms": r(fs.t_total_ms.mean(), 2),
        "llm_share_of_total": r(fs.t_llm_ms.sum() / fs.t_total_ms.sum(), 6),
        "mean_traversal_ms": r(fs.t_traversal_ms.mean(), 4),
    }

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()
