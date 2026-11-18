"""Paired statistics for the revision, including the fair baselines.

Produces the numbers quoted in the paper's Results section:

  * per-system means with a 95% CI over *queries* (descriptive only -- queries
    are not independent samples across systems, so no CI-based claim of
    significance is made);
  * McNemar exact tests for paired binary outcomes (Hits@1, ac1) between the
    full system and each contrast, with Holm correction over the family;
  * Wilcoxon signed-rank for paired continuous outcomes (GSR);
  * effect sizes (odds ratio for McNemar, rank-biserial for Wilcoxon).

Pairing is on `qid` within the same 500-query benchmark, so both systems saw
the identical question -- repeat queries are never treated as extra samples.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def wilcoxon(a, b) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    nz = d[d != 0]
    if len(nz) < 10:
        return {"p": np.nan, "rb": np.nan, "n_nonzero": len(nz)}
    try:
        r = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        p = float(r.pvalue)
    except Exception:
        p = np.nan
    ranks = stats.rankdata(np.abs(nz))
    rb = (ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum()
    return {"p": p, "rb": float(rb), "n_nonzero": len(nz)}


def mcnemar(a, b) -> dict:
    a = np.asarray(a).astype(int)
    b = np.asarray(b).astype(int)
    n01 = int(((a == 0) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum())
    n = n01 + n10
    if n == 0:
        return {"p": 1.0, "or": np.nan, "n_disc": 0, "a_wins": 0, "b_wins": 0}
    p = float(stats.binomtest(n10, n, 0.5, alternative="two-sided").pvalue)
    or_ = (n10 / n01) if n01 else float("inf")
    return {"p": p, "or": or_, "n_disc": n, "a_wins": n10, "b_wins": n01}


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * ps[i])
        adj[i] = min(1.0, run)
    return list(adj)


def ci95(v) -> tuple[float, float]:
    v = np.asarray(v, float)
    if len(v) < 2:
        return (np.nan, np.nan)
    se = v.std(ddof=1) / math.sqrt(len(v))
    return (v.mean() - 1.96 * se, v.mean() + 1.96 * se)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--baselines", default="")
    ap.add_argument("--out", default="results/stats")
    ap.add_argument("--reference", default="full_system")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    m = pd.read_csv(args.main)
    m = m.rename(columns={"success_strict": "ac1"})
    m["ac1"] = pd.to_numeric(m["ac1"], errors="coerce")
    m["vic"] = pd.to_numeric(m["evidence_grounded"], errors="coerce")
    for c in ("hits1", "mrr", "gsr"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    frames = [m]
    if args.baselines and Path(args.baselines).exists():
        b = pd.read_csv(args.baselines).rename(columns={"system": "variant"})
        for c in ("hits1", "mrr", "ac1", "vic", "gsr"):
            b[c] = pd.to_numeric(b[c], errors="coerce")
        frames.append(b)
    df = pd.concat(frames, ignore_index=True)

    # ---- descriptive summary with query-level CI -------------------------
    rows = []
    for v, g in df.groupby("variant"):
        r = {"variant": v, "n": len(g)}
        for c in ("hits1", "mrr", "ac1", "vic", "gsr"):
            mean = float(g[c].mean())
            lo, hi = ci95(g[c].dropna())
            r[f"{c}_mean"] = round(mean, 6)
            r[f"{c}_ci_low"] = round(lo, 6)
            r[f"{c}_ci_high"] = round(hi, 6)
        rows.append(r)
    desc = pd.DataFrame(rows).sort_values("ac1_mean", ascending=False)
    desc.to_csv(out / "descriptive.csv", index=False, encoding="utf-8-sig")

    # ---- paired tests against the reference ------------------------------
    ref = df[df.variant == args.reference][["qid", "hits1", "ac1", "gsr"]]
    if ref.empty:
        raise SystemExit(f"reference variant {args.reference} not found")

    tests = []
    for v in sorted(set(df.variant) - {args.reference}):
        g = df[df.variant == v][["qid", "hits1", "ac1", "gsr"]]
        j = ref.merge(g, on="qid", suffixes=("_ref", "_x")).dropna(
            subset=["hits1_ref", "hits1_x"])
        if j.empty:
            continue
        for metric, kind in (("hits1", "mcnemar"), ("ac1", "mcnemar"),
                             ("gsr", "wilcoxon")):
            a = j[f"{metric}_ref"].values
            b_ = j[f"{metric}_x"].values
            r = mcnemar(a, b_) if kind == "mcnemar" else wilcoxon(a, b_)
            tests.append({
                "contrast": f"{args.reference} vs {v}", "variant": v,
                "metric": metric, "test": kind, "n_pairs": len(j),
                "mean_ref": round(float(np.mean(a)), 6),
                "mean_x": round(float(np.mean(b_)), 6),
                "diff": round(float(np.mean(a) - np.mean(b_)), 6),
                "p_raw": r["p"],
                "effect": r.get("or", r.get("rb")),
                "n_disc": r.get("n_disc", r.get("n_nonzero")),
            })
    t = pd.DataFrame(tests)
    if not t.empty:
        # Holm within each metric family (the natural family for "which
        # contrasts differ on this metric")
        t["p_holm"] = np.nan
        for metric, idx in t.groupby("metric").groups.items():
            t.loc[idx, "p_holm"] = holm(list(t.loc[idx, "p_raw"]))
        t["significant_0.05"] = (t.p_holm < 0.05).astype(int)
        t.to_csv(out / "pairwise_tests.csv", index=False, encoding="utf-8-sig")

    (out / "stats_config.json").write_text(json.dumps(
        {"reference": args.reference, "n_variants": int(df.variant.nunique()),
         "main": args.main, "baselines": args.baselines,
         "n_queries": int(df[df.variant == args.reference].shape[0])},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(desc.to_string(index=False))
    if not t.empty:
        print()
        print(t[["contrast", "metric", "n_pairs", "mean_ref", "mean_x",
                 "diff", "p_raw", "p_holm", "effect"]].to_string(index=False))


if __name__ == "__main__":
    main()
