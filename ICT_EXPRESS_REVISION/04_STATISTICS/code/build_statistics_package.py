"""Revision Stage 5: consolidate statistical tests, effects, and intervals.

Inputs are existing saved results from Phase 1, the revision matched-supervision
stage, the expanded Wikidata stage, the unified latency stage, and the saved
alignment-probe per-query file. No experiment is rerun here.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
REV = ROOT / "ICT_EXPRESS_REVISION"
OUT = REV / "04_STATISTICS" / "results"
OUT.mkdir(parents=True, exist_ok=True)

PHASE1_STATS = ROOT / "ICT_EXPRESS_PHASE1" / "statistical_verification" / "STATISTICAL_RESULTS.csv"
MATCHED = REV / "01_MATCHED_SUPERVISION" / "results" / "MATCHED_SUPERVISION_STATISTICS.csv"
WIKIDATA = REV / "03_WIKIDATA" / "results" / "WIKIDATA_EXPERIMENT_RESULTS.csv"
LATENCY_RAW = REV / "02_LATENCY" / "results" / "LATENCY_RAW_RUNS.csv"
PROBE = ROOT / "ict_express_submission" / "results" / "main" / "alignment_probe" / "probe_per_query.csv"

UNIFIED_COLS = [
    "source", "contrast", "metric", "method", "n", "n_discordant", "statistic",
    "p_raw", "p_holm", "mean_ref", "mean_contrast", "diff", "effect",
    "effect_value", "ci95_low", "ci95_high", "notes",
]


def cp_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def parse_ci(value) -> tuple[float | None, float | None]:
    if pd.isna(value):
        return None, None
    s = str(value).strip().strip("[]")
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def add_unified(rows: list[dict], **kwargs) -> None:
    row = {c: None for c in UNIFIED_COLS}
    row.update(kwargs)
    rows.append(row)


def main() -> None:
    unified: list[dict] = []

    # 1. Phase 1 main 500-query tests.
    p1 = pd.read_csv(PHASE1_STATS)
    for r in p1.itertuples(index=False):
        lo, hi = parse_ci(r.effect_value)
        if r.test == "exact binomial CI (Clopper-Pearson)" or str(r.effect).startswith("ci95"):
            mean_ref = r.mean_ref
            mean_contrast = r.mean_ref
            effect = "proportion"
            effect_value = r.mean_ref
            lo, hi = parse_ci(r.effect_value)
            notes = r.p_holm if isinstance(r.p_holm, str) else None
        else:
            mean_ref = r.mean_ref
            mean_contrast = r.mean_contrast
            effect = r.effect
            effect_value = r.effect_value
            notes = None
        add_unified(
            unified, source="phase1_500", contrast=r.contrast, metric=r.metric,
            method=r.test, n=int(r.n_pairs),
            n_discordant=(None if pd.isna(r.n_discordant) else int(r.n_discordant)),
            statistic=(None if pd.isna(r.statistic) else float(r.statistic)),
            p_raw=(None if pd.isna(r.p_raw) else float(r.p_raw)),
            p_holm=(None if pd.isna(r.p_holm) else float(r.p_holm)),
            mean_ref=(None if pd.isna(mean_ref) else float(mean_ref)),
            mean_contrast=(None if pd.isna(mean_contrast) else float(mean_contrast)),
            effect=effect,
            effect_value=(None if pd.isna(effect_value) else effect_value),
            ci95_low=lo, ci95_high=hi, notes=notes,
        )

    # 2. Revision matched-supervision contrasts.
    m = pd.read_csv(MATCHED)
    for r in m.itertuples(index=False):
        effect = "odds_ratio" if r.metric == "ac1" else "mean_diff"
        eff = r.odds_ratio if r.metric == "ac1" else r.diff
        add_unified(
            unified, source="revision_matched", contrast=r.scope, metric=r.metric,
            method=r.test, n=int(r.n), n_discordant=int(r.n_discordant),
            p_raw=float(r.p_exact), p_holm=float(r.p_holm),
            mean_ref=float(r.mean_ref), mean_contrast=float(r.mean_nonllm),
            diff=float(r.diff), effect=effect, effect_value=eff,
            ci95_low=float(r.ci95_low), ci95_high=float(r.ci95_high),
            notes="LLM planner vs deterministic traversal under matched alignment",
        )

    # 3. Alignment probe recomputed from saved per-query records. The
    # policy-relevant stratum is cross-lingual queries whose gold URI was not
    # exposed; the overall gold_absent row mixes in 2-hop queries and is not
    # used for the headline claim.
    probe = pd.read_csv(PROBE, encoding="utf-8-sig")
    probe["gold_in_prompt"] = probe.gold_in_prompt.astype(int)
    for category, cg in probe.groupby("category"):
        for flag, name in [(1, "gold_in_prompt"), (0, "gold_absent")]:
            g = cg[cg.gold_in_prompt == flag]
            if g.empty:
                continue
            k = int((g.hits1 == 1).sum())
            n = int(len(g))
            lo, hi = cp_ci(k, n)
            add_unified(
                unified, source="revision_probe",
                contrast=f"{category}_{name}", metric="hits1",
                method="Clopper-Pearson exact CI", n=n, p_raw=None, p_holm=None,
                mean_ref=k / n, mean_contrast=k / n, effect="proportion",
                effect_value=k / n, ci95_low=lo, ci95_high=hi,
                notes=f"{k}/{n} observed successes; descriptive interval, not a test",
            )

    # 4. Expanded Wikidata descriptive results.
    w = pd.read_csv(WIKIDATA)
    for r in w.itertuples(index=False):
        if r.slice_by != "ALL":
            continue
        contrast = f"wikidata_{r.family}_{r.group}"
        add_unified(
            unified, source="revision_wikidata", contrast=contrast,
            metric="ac1", method="Clopper-Pearson exact CI", n=int(r.n),
            p_raw=None, p_holm=None, mean_ref=float(r.ac1),
            mean_contrast=float(r.ac1), effect="proportion",
            effect_value=float(r.ac1), ci95_low=float(r.ac1_ci95_low),
            ci95_high=float(r.ac1_ci95_high),
            notes=f"family={r.family}; successes={int(r.ac1_successes)}",
        )
        if r.family == "cross-lingual" and r.group == "MATCHED_SUPERVISION":
            for split_name, sub in [("train", "train"), ("held_out", "held-out")]:
                s = w[(w.slice_by == "split") & (w.slice == sub) &
                      (w.family == "cross-lingual") &
                      (w.group == "MATCHED_SUPERVISION")].iloc[0]
                add_unified(
                    unified, source="revision_wikidata",
                    contrast=f"wikidata_cross_lingual_matched_{split_name}",
                    metric="ac1", method="Clopper-Pearson exact CI",
                    n=int(s.n), effect="proportion", effect_value=float(s.ac1),
                    mean_ref=float(s.ac1), mean_contrast=float(s.ac1),
                    ci95_low=float(s.ac1_ci95_low), ci95_high=float(s.ac1_ci95_high),
                    notes=f"successes={int(s.ac1_successes)}",
                )

    # 5. Latency medians with deterministic bootstrap CIs.
    lat_raw = pd.read_csv(LATENCY_RAW)
    rng = np.random.default_rng(20260101)
    for variant, g in lat_raw.groupby("variant"):
        x = g.wall_ms.to_numpy()
        boot = np.median(rng.choice(x, size=(10000, len(x)), replace=True), axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        add_unified(
            unified, source="revision_latency", contrast=variant,
            metric="median_service_ms", method="bootstrap percentile (B=10000)",
            n=int(len(x)), effect="median_ms", effect_value=float(np.median(x)),
            ci95_low=float(lo), ci95_high=float(hi),
            notes="serial service time; 24-qid unified workload; no queueing",
        )

    unified_df = pd.DataFrame(unified)[UNIFIED_COLS]
    unified_df.to_csv(OUT / "STATISTICAL_RESULTS.csv", index=False)

    # Effect-size table, including a transparent OR-to-r transform.
    eff_rows: list[dict] = []
    for r in unified_df.itertuples(index=False):
        if r.effect is None or pd.isna(r.effect_value):
            continue
        eff_rows.append({
            "source": r.source, "contrast": r.contrast, "metric": r.metric,
            "effect": r.effect, "effect_value": r.effect_value,
            "ci95_low": r.ci95_low, "ci95_high": r.ci95_high,
            "interpretation": "as reported by source test",
        })
        if r.effect == "odds_ratio":
            try:
                odds = float(r.effect_value)
                rr = (odds - 1) / (odds + 1)
                eff_rows.append({
                    "source": r.source, "contrast": r.contrast, "metric": r.metric,
                    "effect": "odds_to_r", "effect_value": rr,
                    "ci95_low": None, "ci95_high": None,
                    "interpretation": "derived (OR-1)/(OR+1); descriptive only",
                })
            except (TypeError, ValueError):
                pass
    pd.DataFrame(eff_rows).to_csv(OUT / "EFFECT_SIZE_RESULTS.csv", index=False)

    ci_rows: list[dict] = []
    for r in unified_df.itertuples(index=False):
        if r.ci95_low is None or pd.isna(r.ci95_low):
            continue
        ci_rows.append({
            "source": r.source, "contrast": r.contrast, "metric": r.metric,
            "method": r.method, "n": r.n, "estimate": r.effect_value,
            "ci95_low": r.ci95_low, "ci95_high": r.ci95_high,
        })
    pd.DataFrame(ci_rows).to_csv(OUT / "CONFIDENCE_INTERVAL_RESULTS.csv", index=False)

    print(f"unified_rows={len(unified_df)} effect_rows={len(eff_rows)} ci_rows={len(ci_rows)}")


if __name__ == "__main__":
    main()
