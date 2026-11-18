"""P1 Stage 6: reanalyse GSR without claiming whole-system O(1) complexity.

Writes:
  05_GSR_ANALYSIS/results/GSR_REANALYSIS.csv
  05_GSR_ANALYSIS/results/GSR_REGRESSION_RESULTS.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
SRC = ROOT / "ict_express_submission/results/scaling/scaling.csv"
OUT = ROOT / "ICT_EXPRESS_REVISION/05_GSR_ANALYSIS/results"


def main() -> None:
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    rows = []
    for (variant, triples), g in df.groupby(["variant", "triples"]):
        rows.append({
            "variant": variant, "triples": int(triples), "n_queries": int(g.n.sum()),
            "mean_triples_scanned": float(g.triples_scanned.mean()),
            "median_triples_scanned": float(g.triples_scanned.median()),
            "mean_gsr": float(g.gsr.mean()),
            "mean_ms": float(g.mean_ms.mean()),
            "mean_traversal_ms": float(g.mean_traversal_ms.mean()),
            "ac1": float(g.ac1.mean()),
        })
    rean = pd.DataFrame(rows).sort_values(["variant", "triples"])

    fits = []
    for variant, g in rean.groupby("variant"):
        x = np.log(g.triples.to_numpy(dtype=float))
        for metric, col in [("gsr", "mean_gsr"),
                            ("triples_scanned", "mean_triples_scanned"),
                            ("mean_ms", "mean_ms")]:
            y = np.log(g[col].to_numpy(dtype=float))
            slope, intercept = np.polyfit(x, y, 1)
            yhat = slope * x + intercept
            ss_res = float(((y - yhat) ** 2).sum())
            ss_tot = float(((y - y.mean()) ** 2).sum())
            r2 = 1 - ss_res / ss_tot if ss_tot else np.nan
            fits.append({
                "variant": variant, "metric": metric, "exponent": round(float(slope), 4),
                "r2": round(float(r2), 6), "n_points": len(g),
            })
    fit_df = pd.DataFrame(fits)

    OUT.mkdir(parents=True, exist_ok=True)
    rean.to_csv(OUT / "GSR_REANALYSIS.csv", index=False)
    fit_df.to_csv(OUT / "GSR_REGRESSION_RESULTS.csv", index=False)
    print(rean.to_string(index=False))
    print()
    print(fit_df.to_string(index=False))


if __name__ == "__main__":
    main()
