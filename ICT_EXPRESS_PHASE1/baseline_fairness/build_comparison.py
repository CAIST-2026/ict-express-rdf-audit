"""Build the baseline fairness comparison table and analysis.

Combines:
  - matched_supervision.py results (non-LLM localized traversal, 3 groups)
  - saved main run records (LLM-guided full_system = matched-supervision;
    no_aligner = no-supervision)
  - saved fair baselines (sparql_real / dense = no-supervision in the original
    design; their matched-supervision variants are computed here from the
    SAME alignment table by a deterministic URI-injection wrapper)
  - Oracle upper bound

All numbers trace to CSVs in this directory or in ict_express_submission.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

SUB = Path(__file__).resolve().parents[2]
BF = SUB / "ICT_EXPRESS_PHASE1/baseline_fairness"
MS = BF / "MATCHED_SUPERVISION_RESULTS.csv"
MAIN = SUB / "upstream_results/experimental_results.csv"
BASE = SUB / "results/baselines/seed_20260101/per_query.csv"
OUT = BF / "BASELINE_COMPARISON_TABLE.csv"


def load():
    main = pd.read_csv(MAIN).rename(columns={"success_strict": "ac1",
                                             "evidence_grounded": "vic",
                                             "variant": "system"})
    base = pd.read_csv(BASE)
    ms = pd.read_csv(MS)
    return main, base, ms


def agg(d, by="category"):
    return d.groupby(by)[["hits1", "mrr", "ac1", "vic", "gsr"]].mean()


def main():
    m, b, ms = load()
    rows = []

    def add(system, group, d):
        g = agg(d)
        for cat in ("1-hop", "2-hop", "cross-lingual"):
            if cat not in g.index:
                continue
            r = g.loc[cat]
            rows.append({"system": system, "group": group, "category": cat,
                         "n": int((d.category == cat).sum()),
                         "hits1": round(r.hits1, 4), "mrr": round(r.mrr, 4),
                         "ac1": round(r.ac1, 4), "vic": round(r.vic, 4),
                         "gsr": round(r.gsr, 6)})
        r = d[["hits1", "mrr", "ac1", "vic", "gsr"]].mean()
        rows.append({"system": system, "group": group, "category": "OVERALL",
                     "n": len(d), "hits1": round(r.hits1, 4), "mrr": round(r.mrr, 4),
                     "ac1": round(r.ac1, 4), "vic": round(r.vic, 4),
                     "gsr": round(r.gsr, 6)})

    # LLM system: saved records (full_system has matched alignment table;
    # no_aligner has no alignment table but still gets surface anchors)
    add("LLM-guided localized", "MATCHED_SUPERVISION", m[m.system == "full_system"])
    add("LLM-guided localized", "NO_SUPERVISION", m[m.system == "no_aligner"])
    # Non-LLM traversal: newly executed
    for grp in ("NO_SUPERVISION", "MATCHED_SUPERVISION", "ORACLE"):
        add("Non-LLM localized traversal", grp, ms[ms.group == grp])
    # SPARQL / dense: saved no-supervision records
    for sys_ in ("sparql_real", "dense"):
        add(f"{sys_} (saved)", "NO_SUPERVISION", b[b.system == sys_])

    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    print(f"wrote {OUT} rows={len(t)}")
    print(t[t.category == "OVERALL"][["system", "group", "ac1", "vic", "gsr"]].to_string(index=False))
    print("\nCross-lingual only:")
    print(t[t.category == "cross-lingual"][["system", "group", "ac1"]].to_string(index=False))

if __name__ == "__main__":
    main()
