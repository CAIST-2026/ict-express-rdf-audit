"""Generate review figures from saved statistical results (stdlib only)."""
from __future__ import annotations

import html
import math
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/yuxiangsun/Desktop/ICT/ICT_EXPRESS_REVISION/04_STATISTICS")
CI = ROOT / "results" / "CONFIDENCE_INTERVAL_RESULTS.csv"
LAT = ROOT / "results" / "STATISTICAL_RESULTS.csv"
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def esc(x) -> str:
    return html.escape(str(x))


def accuracy_ci_figure() -> None:
    ci = pd.read_csv(CI)
    selected = []
    for contrast in ["full_system", "sparql_real", "dense", "sparql_baseline"]:
        r = ci[(ci.source == "phase1_500") & (ci.contrast == contrast) &
               (ci.metric == "ac1")]
        if not r.empty:
            selected.append((contrast, float(r.iloc[0].estimate),
                             float(r.iloc[0].ci95_low), float(r.iloc[0].ci95_high),
                             "500-query ac1"))
    r = ci[(ci.source == "revision_matched") &
           (ci.contrast == "overall_500") & (ci.metric == "ac1")]
    selected.append(("matched_nonllm", float(r.iloc[0].estimate),
                     float(r.iloc[0].ci95_low), float(r.iloc[0].ci95_high),
                     "matched supervision"))
    for name, label in [("cross-lingual_gold_in_prompt", "cross-lingual / exposed"),
                        ("cross-lingual_gold_absent", "cross-lingual / unexposed")]:
        r = ci[(ci.source == "revision_probe") & (ci.contrast == name)]
        selected.append((label, float(r.iloc[0].estimate),
                         float(r.iloc[0].ci95_low), float(r.iloc[0].ci95_high),
                         "exact CI"))

    w, h, left, right = 820, 430, 210, 80
    plot_w = w - left - right
    y0, dy = 52, 46
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="20" y="28" font-family="Arial" font-size="16" fill="#222">Accuracy with 95% confidence intervals</text>']
    for tick in range(0, 11):
        x = left + plot_w * tick / 10
        parts.append(f'<line x1="{x:.1f}" y1="40" x2="{x:.1f}" y2="{y0 + dy * len(selected):.1f}" stroke="#e6e6e6"/>')
        parts.append(f'<text x="{x:.1f}" y="{y0 + dy * len(selected) + 16}" font-family="Arial" font-size="11" fill="#555" text-anchor="middle">{tick/10:.1f}</text>')
    for i, (label, est, lo, hi, tag) in enumerate(selected):
        y = y0 + dy * i
        x_est = left + plot_w * est
        x_lo = left + plot_w * lo
        x_hi = left + plot_w * hi
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" font-family="Arial" font-size="12" fill="#222" text-anchor="end">{esc(label)}</text>')
        parts.append(f'<line x1="{x_lo:.1f}" y1="{y:.1f}" x2="{x_hi:.1f}" y2="{y:.1f}" stroke="#2b6cb0" stroke-width="3"/>')
        parts.append(f'<line x1="{x_lo:.1f}" y1="{y-5:.1f}" x2="{x_lo:.1f}" y2="{y+5:.1f}" stroke="#2b6cb0"/>')
        parts.append(f'<line x1="{x_hi:.1f}" y1="{y-5:.1f}" x2="{x_hi:.1f}" y2="{y+5:.1f}" stroke="#2b6cb0"/>')
        parts.append(f'<circle cx="{x_est:.1f}" cy="{y:.1f}" r="4" fill="#c53030"/>')
        parts.append(f'<text x="{x_hi+8:.1f}" y="{y+4:.1f}" font-family="Arial" font-size="11" fill="#555">{est:.3f} ({tag})</text>')
    parts.append('</svg>')
    (FIG / "accuracy_ci.svg").write_text("\n".join(parts), encoding="utf-8")


def latency_figure() -> None:
    lat = pd.read_csv(LAT)
    g = lat[(lat.source == "revision_latency") &
            (lat.metric == "median_service_ms")].copy()
    g["median"] = pd.to_numeric(g.effect_value)
    g = g.sort_values("median")
    w, h, left, right = 820, 360, 190, 100
    plot_w = w - left - right
    y0, dy = 52, 44
    logmin, logmax = math.log10(0.05), math.log10(20000)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="20" y="28" font-family="Arial" font-size="16" fill="#222">Unified-workload median service time (log scale)</text>']
    for exp in [-1, 0, 1, 2, 3, 4]:
        tick = 10 ** exp
        x = left + plot_w * (math.log10(tick) - logmin) / (logmax - logmin)
        parts.append(f'<line x1="{x:.1f}" y1="40" x2="{x:.1f}" y2="{y0 + dy * len(g):.1f}" stroke="#e6e6e6"/>')
        parts.append(f'<text x="{x:.1f}" y="{y0 + dy * len(g) + 16}" font-family="Arial" font-size="11" fill="#555" text-anchor="middle">{tick:g}</text>')
    for i, r in enumerate(g.itertuples(index=False)):
        y = y0 + dy * i
        x = left + plot_w * (math.log10(max(r.median, 0.05)) - logmin) / (logmax - logmin)
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" font-family="Arial" font-size="12" fill="#222" text-anchor="end">{esc(r.contrast)}</text>')
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#2b6cb0" stroke-width="10"/>')
        parts.append(f'<text x="{x+8:.1f}" y="{y+4:.1f}" font-family="Arial" font-size="11" fill="#333">{r.median:.3f} ms</text>')
    parts.append(f'<text x="{left + plot_w/2:.1f}" y="{h-12}" font-family="Arial" font-size="11" fill="#555" text-anchor="middle">milliseconds</text>')
    parts.append('</svg>')
    (FIG / "latency_median.svg").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    accuracy_ci_figure()
    latency_figure()
    print("wrote accuracy_ci.svg and latency_median.svg")
