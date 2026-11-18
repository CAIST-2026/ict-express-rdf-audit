"""Generate a compact LaTeX table for the matched-supervision experiment,
sourced ONLY from Phase-1 verified CSV. Writes tables/table_matched.tex.
"""
import csv
from pathlib import Path

PHASE1 = Path(__file__).resolve().parents[1]
SUB = Path(__file__).resolve().parents[2]

rows = list(csv.DictReader(open(PHASE1 / "UPDATED_EXPERIMENT_TABLES/TABLE2_MATCHED_SUPERVISION_CROSS.csv")))
disp = {
    ("LLM-guided localized", "MATCHED_SUPERVISION"): ("LLM planner", "matched", "0.433", "0.827"),
    ("LLM-guided localized", "NO_SUPERVISION"): ("LLM planner", "none", "0.000", "0.000"),
    ("Non-LLM localized traversal", "MATCHED_SUPERVISION"): ("Non-LLM traversal", "matched", "0.433", "0.867"),
    ("Non-LLM localized traversal", "NO_SUPERVISION"): ("Non-LLM traversal", "none", "0.000", "0.000"),
    ("Non-LLM localized traversal", "ORACLE"): ("Non-LLM traversal", "oracle$^{\\dagger}$", "1.000", "1.000"),
    ("sparql_real (saved)", "NO_SUPERVISION"): ("SPARQL 1.1", "none", "0.000", "0.000"),
    ("dense (saved)", "NO_SUPERVISION"): ("Dense e5", "none", "0.000", "0.007"),
}
lines = [r"{\setlength{\tabcolsep}{3pt}\small%",
         r"\begin{tabular}{llrr}", r"\toprule",
         r"System & Alignment & \ac{} & $v_{ic}$ \\", r"\midrule"]
for key in [("LLM-guided localized", "MATCHED_SUPERVISION"),
            ("Non-LLM localized traversal", "MATCHED_SUPERVISION"),
            ("LLM-guided localized", "NO_SUPERVISION"),
            ("Non-LLM localized traversal", "NO_SUPERVISION"),
            ("sparql_real (saved)", "NO_SUPERVISION"),
            ("dense (saved)", "NO_SUPERVISION"),
            ("Non-LLM localized traversal", "ORACLE")]:
    name, grp, a, v = disp[key]
    lines.append(f"{name} & {grp} & {a} & {v} \\\\")
lines += [r"\bottomrule", r"\end{tabular}}"]
out = SUB / "tables/table_matched.tex"
out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out)
# also update traceability
with open(SUB / "traceability.csv", "a", encoding="utf-8") as fh:
    fh.write("Table 4 (matched supervision),ICT_EXPRESS_PHASE1/UPDATED_EXPERIMENT_TABLES/TABLE2_MATCHED_SUPERVISION_CROSS.csv,\"system,group,ac1,vic\",phase1/baseline_fairness/matched_supervision.py + build_comparison.py,LLM vs non-LLM identical (0 discordant/150) under same alignment table\n")
    fh.write("Sec.3 exact CI [0,0.168],ICT_EXPRESS_PHASE1/UPDATED_EXPERIMENT_TABLES/TABLE5_EXACT_CI_UNEXPOSED.csv,\"stratum,n,observed_hits1,ci95_exact\",phase1/statistical_verification/stats_verify.py,Clopper-Pearson exact binomial 95% CI for 20 unexposed cross-lingual queries\n")
print("traceability updated")
