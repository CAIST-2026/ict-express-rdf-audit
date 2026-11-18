"""Task D — statistical verification from saved per-query records.

Recomputes McNemar exact, Wilcoxon signed-rank, Holm correction, 95% CIs,
effect sizes, and exact binomial CIs (notably for the 20 unexposed
cross-lingual queries with zero observed hits).
"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

SUB = Path(__file__).resolve().parents[2]
MAIN = SUB / "upstream_results" / "experimental_results.csv"
BASE = SUB / "results" / "baselines" / "seed_20260101" / "per_query.csv"
PROBE = SUB / "results" / "main" / "alignment_probe" / "probe_by_group.csv"
OUT = SUB / "ICT_EXPRESS_PHASE1/statistical_verification/STATISTICAL_RESULTS.csv"


def norm(d):
    return d.rename(columns={"success_strict": "ac1", "evidence_grounded": "vic",
                             "context_triples": "ctx_triples", "variant": "system"})


def mcnemar_exact(a, b):
    """Two-sided exact McNemar on paired binary vectors a (ref), b (contrast)."""
    n01 = int(((a == 1) & (b == 0)).sum())
    n10 = int(((a == 0) & (b == 1)).sum())
    n = n01 + n10
    if n == 0:
        return n01, n10, 1.0
    p = 2 * stats.binom.cdf(min(n01, n10), n, 0.5)
    return n01, n10, min(1.0, float(p))


def wilcoxon(a, b):
    d = np.asarray(a) - np.asarray(b)
    if np.allclose(d, 0):
        return 0.0, 1.0
    try:
        r = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        return float(r.statistic), float(r.pvalue)
    except ValueError:
        return float("nan"), 1.0


def holm(pvals):
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (m - i) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return max(0.0, c-h), min(1.0, c+h)


def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial CI."""
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha/2, k, n-k+1)
    hi = 1.0 if k == n else stats.beta.ppf(1-alpha/2, k+1, n-k)
    return float(lo), float(hi)


def main():
    m = norm(pd.read_csv(MAIN))
    b = pd.read_csv(BASE)
    fs = m[m.system == "full_system"].set_index("qid").sort_index()

    rows = []

    # --- pairwise: full_system vs every contrast on hits1 and ac1 (McNemar) ---
    contrasts = []
    for sys_ in m.system.unique():
        if sys_ != "full_system":
            d = m[m.system == sys_].set_index("qid").sort_index()
            contrasts.append((sys_, d))
    for sys_ in b.system.unique():
        contrasts.append((sys_, b[b.system == sys_].set_index("qid").sort_index()))

    for metric in ("hits1", "ac1"):
        raw = []
        for name, d in contrasts:
            a = fs[metric].reindex(d.index).to_numpy()
            x = d[metric].to_numpy()
            n01, n10, p = mcnemar_exact(a, x)
            # odds ratio (with Haldane correction)
            orv = (n01 + 0.5) / (n10 + 0.5) if (n01 + n10) else float("nan")
            raw.append({"contrast": name, "metric": metric, "test": "McNemar exact",
                        "n_pairs": int(len(a)), "n_discordant": n01+n10,
                        "b_ref_win": n01, "c_contrast_win": n10,
                        "statistic": float("nan"), "p_raw": p, "effect": "odds_ratio",
                        "effect_value": float(orv),
                        "mean_ref": float(np.mean(a)), "mean_contrast": float(np.mean(x))})
        pads = holm([r["p_raw"] for r in raw])
        for r, padj in zip(raw, pads):
            r["p_holm"] = float(padj)
            rows.append(r)

    # --- GSR: Wilcoxon signed-rank on paired differences ---
    raw = []
    for name, d in contrasts:
        a = fs.gsr.reindex(d.index).to_numpy()
        x = d.gsr.to_numpy()
        stat, p = wilcoxon(a, x)
        diff = a - x
        raw.append({"contrast": name, "metric": "gsr", "test": "Wilcoxon signed-rank",
                    "n_pairs": int(len(a)), "n_discordant": int(np.sum(diff != 0)),
                    "b_ref_win": int((diff > 0).sum()), "c_contrast_win": int((diff < 0).sum()),
                    "statistic": stat, "p_raw": p, "effect": "mean_diff",
                    "effect_value": float(np.mean(diff)),
                    "mean_ref": float(np.mean(a)), "mean_contrast": float(np.mean(x))})
    pads = holm([r["p_raw"] for r in raw])
    for r, padj in zip(raw, pads):
        r["p_holm"] = float(padj)
        rows.append(r)

    # --- 95% CIs on ac1 for principal systems (Wilson + normal-approx show both) ---
    for name, d in [("full_system", fs)] + [(s, dd) for s, dd in contrasts]:
        k = int(d.ac1.sum()); n = len(d)
        lo, hi = wilson_ci(k, n)
        rows.append({"contrast": name, "metric": "ac1", "test": "95% Wilson CI",
                     "n_pairs": n, "n_discordant": k, "b_ref_win": "", "c_contrast_win": "",
                     "statistic": "", "p_raw": "", "p_holm": "",
                     "effect": "ci95_wilson", "effect_value": f"[{lo:.4f},{hi:.4f}]",
                     "mean_ref": k/n, "mean_contrast": ""})

    # --- exact binomial CI for the 20 unexposed cross-lingual queries ---
    probe = pd.read_csv(PROBE)
    cross = probe[probe.category == "cross-lingual"]
    for _, r in cross.iterrows():
        k_hits = int(round(r.hits1 * r.n))
        lo, hi = clopper_pearson(k_hits, int(r.n))
        wlo, whi = wilson_ci(k_hits, int(r.n))
        rows.append({"contrast": f"cross-lingual:{r.group}", "metric": "hits1",
                     "test": "exact binomial CI (Clopper-Pearson)",
                     "n_pairs": int(r.n), "n_discordant": k_hits,
                     "b_ref_win": "", "c_contrast_win": "", "statistic": "",
                     "p_raw": "", "p_holm": "",
                     "effect": "ci95_exact", "effect_value": f"[{lo:.4f},{hi:.4f}]",
                     "mean_ref": float(r.hits1),
                     "mean_contrast": f"wilson=[{wlo:.4f},{whi:.4f}]"})

    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(t)} rows)")
    # highlight the key result
    key = t[t.contrast == "cross-lingual:gold_absent"]
    print(key[["contrast", "n_pairs", "mean_ref", "effect_value"]].to_string(index=False))

if __name__ == "__main__":
    main()
