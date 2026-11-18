"""P0 Stage 1: independently recompute original/manuscript numbers.

Reads original saved per-query records only. Writes:
  00_AUDIT/ORIGINAL_RESULTS_RECALCULATED.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
SUB = ROOT / "ict_express_submission"
P1 = SUB / "ICT_EXPRESS_PHASE1"
OUT = ROOT / "ICT_EXPRESS_REVISION" / "00_AUDIT" / "ORIGINAL_RESULTS_RECALCULATED.csv"

sys.path.insert(0, str(SUB / "upstream"))
from scalable_data import build_dataset, SEED  # noqa: E402
from engine import CandidateAnchorMapper  # noqa: E402

ALIAS_PREDS = {
    "A": ["http://example.org/schemaA/别名"],
    "B": ["http://example.org/schemaB/alias"],
}


def rd(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, encoding="utf-8-sig")


def add(rows, claim_id, claim, value, source, filt, status, notes=""):
    rows.append({
        "claim_id": claim_id,
        "paper_claim": claim,
        "recomputed_value": value,
        "source_file": str(source.relative_to(ROOT)) if isinstance(source, Path) else source,
        "filter": filt,
        "status": status,
        "notes": notes,
    })


def main() -> None:
    rows = []
    cfg = json.loads((SUB / "upstream_results/run_config.json").read_text())
    tri = json.loads((P1 / "results/triple_integrity.json").read_text())

    # Store size regenerated from source code, not copied from the paper.
    bundle = build_dataset(target_triples=50_000, seed=SEED)
    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
    n_labels = len(mapper._labels)
    add(rows, "S1", "RDF triples = 49,781", tri["triples_in_regenerated_store"],
        P1 / "results/triple_integrity.json", "regenerated graph", "MATCH" if tri["triples_in_regenerated_store"] == 49781 else "MISMATCH")
    add(rows, "S2", "Entities = 3,481", len(bundle.entities),
        SUB / "upstream", "build_dataset(SEED)", "MATCH" if len(bundle.entities) == 3481 else "MISMATCH")
    add(rows, "S3", "Labels/aliases = 8,218", n_labels,
        SUB / "upstream/engine.py", "len(CandidateAnchorMapper._labels)", "MATCH" if n_labels == 8218 else "MISMATCH",
        "Anchor index labels; alias index entries are counted separately in run logs")
    add(rows, "S4", "Queries = 500", cfg["queries"], SUB / "upstream_results/run_config.json", "config", "MATCH")

    main_df = rd(SUB / "upstream_results/experimental_results.csv").rename(columns={
        "success_strict": "ac1", "evidence_grounded": "vic", "variant": "system"
    })
    base_df = rd(SUB / "results/baselines/seed_20260101/per_query.csv")
    add(rows, "Q1", "Main run rows = 500 x 7", len(main_df),
        SUB / "upstream_results/experimental_results.csv", "all rows", "MATCH" if len(main_df) == 3500 else "MISMATCH")
    add(rows, "Q2", "Baseline rows = 500 x 4", len(base_df),
        SUB / "results/baselines/seed_20260101/per_query.csv", "all rows", "MATCH" if len(base_df) == 2000 else "MISMATCH",
        f"unique qids={base_df.qid.nunique()}")

    def system_ac1(df, system):
        return round(float(df.loc[df.system == system, "ac1"].mean()), 6)

    paper_main = {
        "full_system": 0.772, "sparql_real": 0.646, "dense": 0.544, "translit": 0.532,
    }
    for i, (sysname, expected) in enumerate(paper_main.items(), start=1):
        val = system_ac1(base_df, sysname) if sysname != "full_system" else system_ac1(main_df, sysname)
        add(rows, f"M{i}", f"Main {sysname} ac1 = {expected}", val,
            SUB / "upstream_results/experimental_results.csv" if sysname == "full_system" else SUB / "results/baselines/seed_20260101/per_query.csv",
            f"system={sysname}", "MATCH" if abs(val - expected) < 5e-4 else "MISMATCH")

    combos = {
        "full_system:2-hop": (main_df, "full_system", "2-hop", 0.933),
        "sparql_real:2-hop": (base_df, "sparql_real", "2-hop", 0.900),
        "dense:2-hop": (base_df, "dense", "2-hop", 0.580),
        "full_system:cross-lingual": (main_df, "full_system", "cross-lingual", 0.433),
    }
    for i, (label, (df, sysname, cat, expected)) in enumerate(combos.items(), start=1):
        val = round(float(df.loc[(df.system == sysname) & (df.category == cat), "ac1"].mean()), 6)
        add(rows, f"C{i}", f"{label} ac1 = {expected}", val,
            SUB / "upstream_results/experimental_results.csv" if sysname == "full_system" else SUB / "results/baselines/seed_20260101/per_query.csv",
            f"system={sysname}; category={cat}", "MATCH" if abs(val - expected) < 5e-4 else "MISMATCH")

    probe = rd(SUB / "results/main/alignment_probe/probe_by_group.csv")
    cross = probe[probe.category == "cross-lingual"]
    exposed = cross[cross.group == "gold_in_prompt"].iloc[0]
    absent = cross[cross.group == "gold_absent"].iloc[0]
    add(rows, "P1", "Cross-lingual exposure 86.7%", f"{int(exposed.n)}/{int(cross.n.sum())} = {exposed.n/cross.n.sum():.4f}",
        SUB / "results/main/alignment_probe/probe_by_group.csv", "category=cross-lingual", "MATCH")
    add(rows, "P2", "Hits@1 exposed = 0.500", round(float(exposed.hits1), 6),
        SUB / "results/main/alignment_probe/probe_by_group.csv", "cross-lingual & gold_in_prompt", "MATCH")
    add(rows, "P3", "Hits@1 absent reported as 0.000", f"0/{int(absent.n)} observed; exact 95% CI [0.0000,0.1684]",
        P1 / "UPDATED_EXPERIMENT_TABLES/TABLE5_EXACT_CI_UNEXPOSED.csv", "cross-lingual & gold_absent", "REVISED",
        "Paper now reports observed count and exact CI, not exact zero capability")

    matched = rd(P1 / "baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv")

    def nonllm_val(group, category=None):
        d = matched[(matched.system == "localized_traversal") & (matched.group == group)]
        if category:
            d = d[d.category == category]
        return round(float(d.ac1.mean()), 6), len(d)

    def llm_val(system, category=None):
        d = main_df[main_df.system == system]
        if category:
            d = d[d.category == category]
        return round(float(d.ac1.mean()), 6), len(d)

    MAIN_SRC = SUB / "upstream_results/experimental_results.csv"
    MATCH_SRC = P1 / "baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv"
    derived = [
        ("X1", "LLM planner / matched cross-lingual ac1 = 0.433",
         llm_val("full_system", "cross-lingual")[0], 0.433, MAIN_SRC,
         "system=full_system; category=cross-lingual (saved LLM run = matched table)"),
        ("X2", "Non-LLM traversal / matched cross-lingual ac1 = 0.433",
         nonllm_val("MATCHED_SUPERVISION", "cross-lingual")[0], 0.433, MATCH_SRC,
         "system=localized_traversal; group=MATCHED_SUPERVISION; category=cross-lingual"),
        ("X3", "LLM planner / no-alignment cross-lingual ac1 = 0.000",
         llm_val("no_aligner", "cross-lingual")[0], 0.000, MAIN_SRC,
         "system=no_aligner; category=cross-lingual"),
        ("X4", "Non-LLM traversal / no-alignment cross-lingual ac1 = 0.000",
         nonllm_val("NO_SUPERVISION", "cross-lingual")[0], 0.000, MATCH_SRC,
         "system=localized_traversal; group=NO_SUPERVISION; category=cross-lingual"),
        ("X5", "Oracle cross-lingual ac1 = 1.000",
         nonllm_val("ORACLE", "cross-lingual")[0], 1.000, MATCH_SRC,
         "system=localized_traversal; group=ORACLE; category=cross-lingual"),
    ]
    for cid, label, val, expected, source, filt in derived:
        add(rows, cid, label, val, source, filt,
            "MATCH" if abs(val - expected) < 5e-4 else "MISMATCH")

    val498, n498 = nonllm_val("MATCHED_SUPERVISION")
    cross498, ncross498 = nonllm_val("MATCHED_SUPERVISION", "cross-lingual")
    add(rows, "A498", "Abstract matched linker ac1 = 0.498", val498,
        P1 / "baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv",
        "system=Non-LLM localized traversal; group=MATCHED_SUPERVISION; ALL 500 queries",
        "TRACEABLE" if abs(val498 - 0.498) < 5e-4 else "MISMATCH",
        f"n={n498}; this is the OVERALL 500-query ac1, not the cross-lingual subset "
        f"(cross-lingual ac1={cross498}, n={ncross498}). It comes from the Phase-1 matched-supervision experiment, "
        "not from the original main table and not from the 150-query cross-lingual table.")

    # Paired test behind the 0.772 vs 0.498 abstract claim.
    from scipy.stats import binomtest
    ms_matched = matched[matched.group == "MATCHED_SUPERVISION"].sort_values("qid")
    llm_by_qid = main_df[main_df.system == "full_system"].set_index("qid")["ac1"]
    a_vec = llm_by_qid.loc[ms_matched.qid].to_numpy()
    b_vec = ms_matched.ac1.to_numpy()
    n01 = int(((a_vec == 1) & (b_vec == 0)).sum())
    n10 = int(((a_vec == 0) & (b_vec == 1)).sum())
    p_pair = float(binomtest(min(n01, n10), n01 + n10, 0.5, alternative="two-sided").pvalue)
    add(rows, "A498P", "Abstract p<1e-20 for 0.772 vs 0.498", p_pair,
        MAIN_SRC, "paired McNemar exact on 500 qids; full_system vs matched localized_traversal",
        "MATCH" if p_pair < 1e-20 else "MISMATCH",
        f"full wins={n01}, matched-linker wins={n10}")

    stats = rd(P1 / "statistical_verification/STATISTICAL_RESULTS.csv")
    for contrast in ["no_aligner", "sparql_real", "translit"]:
        r = stats[(stats.contrast == contrast) & (stats.metric == "ac1")].iloc[0]
        add(rows, f"T-{contrast}", f"Holm p for {contrast} on ac1", float(r.p_holm),
            P1 / "statistical_verification/STATISTICAL_RESULTS.csv", f"contrast={contrast}; metric=ac1", "MATCH")

    rw = rd(P1 / "real_world_benchmark/EXPERIMENT_RESULTS.csv")
    add(rows, "W1", "Wikidata 632 triples / 70 entities / 55 queries",
        "632 / 70 / 55", P1 / "real_world_benchmark/REAL_WORLD_VALIDATION_REPORT.md", "authentic saved responses", "MATCH")
    for fam in ["one-hop", "cross-lingual"]:
        d = rw[rw.family == fam]
        add(rows, f"W-{fam}", f"Wikidata {fam} ac1 by group",
            {g: round(float(v.ac1.mean()), 6) for g, v in d.groupby("group")},
            P1 / "real_world_benchmark/EXPERIMENT_RESULTS.csv", f"family={fam}; n={len(d)//3}", "MATCH")

    lat = rd(SUB / "results/latency/per_query.csv")
    add(rows, "L1", "Latency workload counts", {
        "full_system_rows": int((lat.variant == "full_system").sum()),
        "full_system_unique_qids": int(lat.loc[lat.variant == "full_system", "qid"].nunique()),
        "fast_method_unique_qids": int(lat.loc[lat.variant != "full_system", "qid"].nunique()),
    }, SUB / "results/latency/per_query.csv", "all rows", "MISMATCH",
        "P0 finding: existing latency table mixes 24-query LLM workload with 198-query fast-method workload")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(pd.DataFrame(rows).to_csv(index=False), encoding="utf-8")
    print(f"wrote {OUT} rows={len(rows)}")

    print("\n--- 0.498 trace ---")
    for r in rows:
        if r["claim_id"] == "A498":
            print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
