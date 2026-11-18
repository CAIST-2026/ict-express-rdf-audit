"""Validate the unified latency workload and compute descriptive contrasts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REV = Path("/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_REVISION/02_LATENCY")
OUT = REV / "results"


def main() -> None:
    raw = pd.read_csv(OUT / "LATENCY_RAW_RUNS.csv")
    summary = pd.read_csv(OUT / "LATENCY_SUMMARY.csv")
    qid_sets = raw.groupby("variant").qid.apply(lambda s: frozenset(s.unique()))
    reference = qid_sets.iloc[0]
    assert all(q == reference for q in qid_sets), "variants use different qids"
    counts = raw.groupby(["variant", "qid"]).size().unstack(fill_value=0)
    assert (counts == 2).all().all(), "unequal repeat counts per qid"
    assert (summary.n_qids == 24).all() and (summary.n_runs == 48).all()

    med = summary.set_index("variant").median_ms
    rows = []
    for variant in summary.variant:
        rows.append({
            "contrast": f"{variant}_vs_full_system",
            "numerator_median_ms": med[variant],
            "denominator_median_ms": med["full_system"],
            "slowdown_vs_full": med[variant] / med["full_system"],
        })
        rows.append({
            "contrast": f"full_system_vs_{variant}",
            "numerator_median_ms": med["full_system"],
            "denominator_median_ms": med[variant],
            "slowdown_vs_full": med["full_system"] / med[variant],
        })
    pd.DataFrame(rows).to_csv(OUT / "LATENCY_CONTRASTS.csv", index=False)
    print("workload_valid=true variants=", len(qid_sets), "qids=", len(reference))


if __name__ == "__main__":
    main()
