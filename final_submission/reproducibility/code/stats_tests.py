"""Multi-seed aggregation and paired significance testing (Phase 2, P5).

Design notes (deliberate, not mechanical):
  * Hits@1 / success are paired *binary* outcomes on the SAME query ids, so the
    matched-pairs test is McNemar's exact test (binomial on the discordant
    pairs), not an independent-samples chi-square.
  * MRR / GSR / latency are paired continuous (or heavily tied) outcomes, so
    Wilcoxon signed-rank is used; with n=500 the normal approximation is fine
    but the exact statistic is reported alongside.
  * Effect sizes: McNemar -> difference of marginal proportions with an odds
    ratio from the discordant pairs; Wilcoxon -> rank-biserial correlation.
  * Multiple comparisons across the family of systems are Holm-corrected.
  * Nothing is written for a comparison that was not actually run: the script
    only reads result files that exist.
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

BINARY = ["hits1", "success_loose", "success_strict", "evidence_grounded"]
CONTINUOUS = ["mrr", "gsr", "faithfulness_proxy", "relevance_proxy", "t_total_ms"]


def bootstrap_ci(values, n_boot: int = 5000, seed: int = 0) -> tuple:
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    means = v[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> dict:
    """a, b: paired binary outcomes (1 = success) for the same items."""
    a = np.asarray(a).astype(int)
    b = np.asarray(b).astype(int)
    n01 = int(((a == 0) & (b == 1)).sum())   # b wins
    n10 = int(((a == 1) & (b == 0)).sum())   # a wins
    n = n01 + n10
    if n == 0:
        return {"test": "McNemar exact", "n_discordant": 0, "b_wins": n01,
                "a_wins": n10, "p_value": 1.0, "odds_ratio": float("nan"),
                "diff": 0.0}
    res = stats.binomtest(n10, n, p=0.5, alternative="two-sided")
    or_ = (n10 / n01) if n01 > 0 else float("inf")
    return {"test": "McNemar exact", "n_discordant": n, "b_wins": n01,
            "a_wins": n10, "p_value": float(res.pvalue),
            "odds_ratio": round(or_, 4) if np.isfinite(or_) else "inf",
            "diff": round(float(a.mean() - b.mean()), 6)}


def wilcoxon_paired(a: np.ndarray, b: np.ndarray) -> dict:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    nz = d[d != 0]
    if len(nz) < 10:
        return {"test": "Wilcoxon signed-rank", "n_nonzero": len(nz),
                "statistic": float("nan"), "p_value": float("nan"),
                "rank_biserial": float("nan")}
    try:
        res = stats.wilcoxon(a, b, zero_method="wilcox",
                             alternative="two-sided", method="auto")
    except TypeError:                                  # older scipy: mode=
        res = stats.wilcoxon(a, b, zero_method="wilcox",
                             alternative="two-sided", mode="auto")
    # rank-biserial correlation from the signed ranks
    r = stats.rankdata(np.abs(nz))
    r_plus = r[nz > 0].sum()
    r_minus = r[nz < 0].sum()
    rb = (r_plus - r_minus) / r.sum()
    return {"test": "Wilcoxon signed-rank", "n_nonzero": len(nz),
            "statistic": float(res.statistic), "p_value": float(res.pvalue),
            "rank_biserial": round(float(rb), 4)}


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return list(adj)


def load_runs(inputs: list[str]) -> dict[str, pd.DataFrame]:
    runs = {}
    for p in inputs:
        path = Path(p)
        if path.is_dir():
            path = path / "experimental_results.csv"
        if not path.exists():
            raise FileNotFoundError(f"results file not found: {path}")
        df = pd.read_csv(path)
        key = path.parent.name if path.parent.name else str(path.parent)
        runs[key] = df
    return runs


def seed_summary(runs: dict[str, pd.DataFrame], metrics: list[str]) -> pd.DataFrame:
    out = []
    for metric in metrics:
        for variant, g in pd.concat(runs.values()).groupby("variant"):
            per_seed = {}
            for name, df in runs.items():
                sub = df[df.variant == variant][metric]
                sub = pd.to_numeric(sub, errors="coerce").dropna()
                if len(sub):
                    per_seed[name] = float(sub.mean())
            vals = list(per_seed.values())
            lo = hi = float("nan")
            if vals:
                if len(vals) >= 2:
                    se = float(np.std(vals, ddof=1) / math.sqrt(len(vals)))
                    half = 1.96 * se if se > 0 else 0.0
                    lo, hi = float(np.mean(vals) - half), float(np.mean(vals) + half)
                else:
                    lo, hi = bootstrap_ci(
                        pd.to_numeric(pd.concat(runs.values()).query(
                            "variant == @variant")[metric],
                            errors="coerce").dropna())
            out.append({
                "metric": metric, "variant": variant, "n_seeds": len(vals),
                "mean": round(float(np.mean(vals)), 6) if vals else "",
                "sd": round(float(np.std(vals, ddof=1)), 6) if len(vals) > 1 else "",
                "ci95_low": round(lo, 6) if np.isfinite(lo) else "",
                "ci95_high": round(hi, 6) if np.isfinite(hi) else "",
                "per_seed": json.dumps(per_seed, ensure_ascii=False),
            })
    return pd.DataFrame(out)


def pairwise(runs: dict[str, pd.DataFrame], metrics: list[str],
             variants: list[str], pair_key: str = "seed") -> pd.DataFrame:
    """Paired tests, computed **within** a seed and pooled across seeds.

    The pairing key must be ``(qid, seed)``: query id 42 of seed A and query id
    42 of seed B are different questions, so merging on ``qid`` alone would
    produce a cross-seed cartesian product and inflate n. Rows are emitted per
    seed, plus one ``pooled`` row family that reuses the same pairing key, which
    is a valid stratified paired test (equal weight per item, no seed mixing).

    ``pair_key="qid"`` is the opt-in used when exactly two runs share the *same*
    query set and differ only in a condition (e.g. coverage 0.92 vs 1.00 on the
    same seed). Pairing then happens **across** the two runs on ``qid`` only --
    never inside a run, which would pair a system with itself.
    """
    if pair_key == "qid":
        names = list(runs)
        if len(names) != 2:
            raise ValueError("pair_key='qid' needs exactly two runs "
                             f"(got {len(names)})")
        # Condition comparison: the SAME variant is paired across the two runs
        # (run A = control, run B = treatment). Pairing different systems across
        # runs would confound the condition with the system.
        units = [(f"{names[0]}|{names[1]}", runs[names[0]], runs[names[1]])]
    else:
        frames = []
        for name, df in runs.items():
            d = df.copy()
            d["seed"] = name
            frames.append(d)
        alldf = pd.concat(frames, ignore_index=True)
        units = [(n, alldf[alldf.seed == n], alldf[alldf.seed == n])
                 for n in runs]
        if len(runs) > 1:
            units.append(("pooled", alldf, alldf))

    rows = []
    for unit_name, dfa, dfb in units:
        fam = []
        if pair_key == "qid":
            combos = [(v, v) for v in variants]
        else:
            combos = list(itertools.combinations(variants, 2))
        for metric in metrics:
            for a, b in combos:
                if pair_key == "qid":
                    ga = dfa[dfa.variant == a][["qid", metric]]
                    gb = dfb[dfb.variant == b][["qid", metric]]
                    m = ga.merge(gb, on="qid", suffixes=("_a", "_b")).dropna()
                    a_lab, b_lab = f"{a}@{unit_name.split('|')[0]}", \
                                   f"{b}@{unit_name.split('|')[1]}"
                else:
                    ga = dfa[dfa.variant == a][["qid", "seed", metric]]
                    gb = dfb[dfb.variant == b][["qid", "seed", metric]]
                    m = ga.merge(gb, on=["qid", "seed"],
                                 suffixes=("_a", "_b")).dropna()
                    a_lab, b_lab = a, b
                if m.empty:
                    continue
                fa = pd.to_numeric(m[f"{metric}_a"]).values
                fb = pd.to_numeric(m[f"{metric}_b"]).values
                if metric in BINARY:
                    r = mcnemar_exact(fa, fb)
                else:
                    r = wilcoxon_paired(fa, fb)
                r.update({"seed": unit_name, "metric": metric,
                          "system_a": a_lab, "system_b": b_lab,
                          "n_pairs": len(m),
                          "mean_a": round(float(np.mean(fa)), 6),
                          "mean_b": round(float(np.mean(fb)), 6)})
                fam.append(r)
        if fam:
            pv = holm([x["p_value"] for x in fam])
            for x, ph in zip(fam, pv):
                x["p_holm"] = ph
            rows.extend(fam)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True,
                    help="result dirs or CSVs (one per seed)")
    ap.add_argument("--metrics", default=",".join(BINARY + CONTINUOUS))
    ap.add_argument("--variants", default="")
    ap.add_argument("--pair-key", choices=("seed", "qid"), default="seed",
                    help="seed: pair within each seed (multi-seed runs); "
                         "qid: pair across runs that share the same query set "
                         "(condition comparison, e.g. coverage 0.92 vs 1.00)")
    ap.add_argument("--out", default="outputs_stats")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = load_runs(args.inputs)
    metrics = [m for m in args.metrics.split(",") if m]
    df = pd.concat(runs.values())
    variants = [v for v in args.variants.split(",") if v] or sorted(
        df.variant.unique())

    s = seed_summary(runs, metrics)
    s.to_csv(out_dir / "seed_summary.csv", index=False, encoding="utf-8-sig")
    p = pairwise(runs, metrics, variants, pair_key=args.pair_key)
    p.to_csv(out_dir / "pairwise_tests.csv", index=False, encoding="utf-8-sig")
    print(s.to_string(index=False))
    print()
    print(p.to_string(index=False))
    print(f"\nWrote {out_dir}/seed_summary.csv and {out_dir}/pairwise_tests.csv")


if __name__ == "__main__":
    main()
