"""Generate UPDATED_EXPERIMENT_TABLES/ from verified Phase-1 data only."""
from __future__ import annotations
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "UPDATED_EXPERIMENT_TABLES"
try:
    TABLES.mkdir(parents=True, exist_ok=True)
except FileExistsError:
    pass

ms = pd.read_csv(ROOT / "baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv")
cmp_ = pd.read_csv(ROOT / "baseline_fairness/BASELINE_COMPARISON_TABLE.csv")
stats = pd.read_csv(ROOT / "statistical_verification/STATISTICAL_RESULTS.csv")
rw = pd.read_csv(ROOT / "real_world_benchmark/EXPERIMENT_RESULTS.csv")
import json
audit = json.loads((ROOT / "results/audit_recompute.json").read_text())

# Table 1: audit verification summary (one row per reported metric)
rows = []
for s, metrics in audit["reported_vs_recomputed"].items():
    for metric, x in metrics.items():
        rows.append({"system": s, "metric": metric, "reported": x["reported"],
                     "recomputed": x["recomputed"], "match": x["match"]})
pd.DataFrame(rows).to_csv(TABLES / "TABLE1_AUDIT_VERIFICATION.csv", index=False)

# Table 2: matched-supervision cross-lingual comparison
cl = cmp_[cmp_.category == "cross-lingual"][["system", "group", "ac1", "vic"]]
cl.to_csv(TABLES / "TABLE2_MATCHED_SUPERVISION_CROSS.csv", index=False)

# Table 3: overall comparison
ov = cmp_[cmp_.category == "OVERALL"][["system", "group", "n", "hits1", "ac1", "vic", "gsr"]]
ov.to_csv(TABLES / "TABLE3_OVERALL_COMPARISON.csv", index=False)

# Table 4: key statistics
key = stats[(stats.metric == "ac1") & (stats.test == "McNemar exact")][
    ["contrast", "p_raw", "p_holm", "effect_value"]].copy()
key.columns = ["contrast", "p_raw", "p_holm", "odds_ratio"]
key.to_csv(TABLES / "TABLE4_PAIRED_TESTS.csv", index=False)

# Table 5: exact binomial CIs
ci = stats[stats.test.str.contains("binomial", na=False)][
    ["contrast", "n_pairs", "mean_ref", "effect_value"]].copy()
ci.columns = ["stratum", "n", "observed_hits1", "ci95_exact"]
ci.to_csv(TABLES / "TABLE5_EXACT_CI_UNEXPOSED.csv", index=False)

# Table 6: real-world
rwt = rw.groupby(["group", "family"])[["hits1", "ac1", "vic"]].mean().round(4).reset_index()
rwt.to_csv(TABLES / "TABLE6_REAL_WORLD.csv", index=False)

print("wrote 6 tables to", TABLES)
for p in sorted(TABLES.glob("*.csv")):
    print(" ", p.name, len(pd.read_csv(p)), "rows")
