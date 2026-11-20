#!/usr/bin/env python3
"""Generate a simple SVG bar chart from P1_Aggregate_Results.csv using stdlib only."""
from __future__ import annotations

import csv
import html
from pathlib import Path

FIX_ROOT = Path(__file__).resolve().parents[2]
COMP_ROOT = Path(__file__).resolve().parents[1]
CSV = FIX_ROOT / 'P1_Aggregate_Results.csv'
OUT = COMP_ROOT / 'figures' / 'wikidata_llm_vs_deterministic.svg'
GROUPS = ['llm_matched', 'deterministic_matched', 'llm_no_alignment', 'oracle']
SLICES = ['one-hop', 'cross-lingual']


def main():
    with CSV.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    values = {}
    for g in GROUPS:
        for s in SLICES:
            hit = next((r for r in rows if r['group'] == g and r['slice'] == s), None)
            values[(g, s)] = float(hit['strict_success']) if hit else 0.0
    W, H = 680, 320
    left, bottom, plot_w, plot_h = 70, 40, 560, 230
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
             '<rect width="100%" height="100%" fill="white"/>']
    for tick in range(6):
        y = bottom + plot_h - tick / 5 * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#333">{tick/5:.1f}</text>')
    group_w = plot_w / len(SLICES)
    bar_w = group_w / (len(GROUPS) + 1)
    for si, s in enumerate(SLICES):
        base = left + si * group_w
        for gi, g in enumerate(GROUPS):
            v = values[(g, s)]
            x = base + bar_w * (gi + 0.5)
            h = v * plot_h
            y = bottom + plot_h - h
            color = ['#4C78A8', '#F58518', '#54A24B', '#BAB0AC'][gi]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*0.8:.1f}" height="{h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x+bar_w*0.4:.1f}" y="{y-3:.1f}" text-anchor="middle" font-size="8" fill="#333">{v:.2f}</text>')
        parts.append(f'<text x="{base+group_w/2:.1f}" y="{bottom+plot_h+18}" text-anchor="middle" font-size="11" fill="#222">{html.escape(s)}</text>')
    for gi, g in enumerate(GROUPS):
        x = left + gi * 135
        color = ['#4C78A8', '#F58518', '#54A24B', '#BAB0AC'][gi]
        parts.append(f'<rect x="{x}" y="16" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{x+14}" y="25" font-size="9" fill="#222">{html.escape(g)}</text>')
    parts.append(f'<text x="{left}" y="{bottom+plot_h+36}" font-size="10" fill="#444">Evidence-constrained accuracy (strict_success); oracle is an upper bound, not deployable.</text>')
    parts.append('</svg>')
    OUT.write_text('\n'.join(parts), encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    main()
