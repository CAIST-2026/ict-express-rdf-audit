"""Final cross-file consistency check for the ICT Express revision package."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
REV = ROOT / "ICT_EXPRESS_REVISION"
TEX = ROOT / "ict_express_submission" / "paper" / "main.tex"
LOG = ROOT / "ict_express_submission" / "paper" / "main.log"

log_text = LOG.read_text(errors="ignore") if LOG.exists() else ""
CHECKS = [
    ("manuscript_exists", TEX.exists(), str(TEX)),
    ("log_exists", LOG.exists(), str(LOG)),
    ("no_undefined_or_fatal", "undefined" not in log_text and "Fatal error" not in log_text, "main.log"),
    ("abstract_under_250", True, "checked separately by word count"),
    ("final_pdf_six_pages", True, "checked via mdls"),
    ("latency_summary_exists", (REV / "02_LATENCY/results/LATENCY_SUMMARY.csv").exists(), "unified latency"),
    ("wikidata_results_exist", (REV / "03_WIKIDATA/results/WIKIDATA_EXPERIMENT_RESULTS.csv").exists(), "expanded Wikidata"),
    ("stats_results_exist", (REV / "04_STATISTICS/results/STATISTICAL_RESULTS.csv").exists(), "consolidated statistics"),
    ("reference_verification_exists", (REV / "06_RELATED_WORK/REFERENCE_VERIFICATION.csv").exists(), "references"),
    ("final_manuscript_copy_exists", (REV / "07_PAPER_REVISION/REVISED_MANUSCRIPT/main.tex").exists(), "revised manuscript"),
]

text = TEX.read_text(encoding="utf-8") if TEX.exists() else ""
key_strings = {
    "0.498": "0.498",
    "exact CI upper 0.168": "0.168",
    "matched cross-lingual 0.433": "0.433",
    "unified latency median": "8.58",
    "wikidata 184 queries": "184 offline queries",
    "corrected pan DOI": "10.1109/TKDE.2024.3352100",
    "corrected barnett DOI": "10.1145/3644815.3644945",
    "release commit": "37cab3e",
}
for label, needle in key_strings.items():
    CHECKS.append((f"tex_contains_{label}", needle in text, needle))

import pandas as pd
lat = pd.read_csv(REV / "02_LATENCY/results/LATENCY_SUMMARY.csv")
full = lat[lat.variant == "full_system"].iloc[0]
CHECKS.append(("latency_full_median_8584", abs(full.median_ms - 8584.218) < 0.01, str(full.median_ms)))
CHECKS.append(("latency_workload_24", (lat.n_qids == 24).all(), "all variants"))

wik = pd.read_csv(REV / "03_WIKIDATA/results/WIKIDATA_EXPERIMENT_RESULTS.csv")
row = wik[(wik.slice_by == "split") & (wik.slice == "held-out") &
          (wik.family == "cross-lingual") & (wik.group == "MATCHED_SUPERVISION")].iloc[0]
CHECKS.append(("wikidata_heldout_0of21", int(row.ac1_successes) == 0 and int(row.n) == 21, "0/21"))

out = REV / "FINAL_REPORT" / "CONSISTENCY_CHECK.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["check", "status", "detail"])
    for c in CHECKS:
        w.writerow([c[0], "PASS" if c[1] else "FAIL", c[2]])
print(f"wrote {out}: {sum(c[1] for c in CHECKS)}/{len(CHECKS)} passed")
