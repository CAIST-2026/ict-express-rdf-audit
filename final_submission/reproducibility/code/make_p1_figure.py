#!/usr/bin/env python3
"""Generate the Wikidata comparison figure from aggregate results only."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'P1_Aggregate_Results.csv'
OUT = ROOT / 'figures' / 'wikidata_llm_vs_deterministic.pdf'


def main():
    with CSV.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    groups = ['llm_matched', 'deterministic_matched', 'llm_no_alignment', 'oracle']
    slices = ['one-hop', 'cross-lingual']
    labels = ['one-hop', 'cross-lingual']
    x = range(len(slices))
    width = 0.2
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for i, g in enumerate(groups):
        vals = []
        for s in slices:
            hit = next((r for r in rows if r['group'] == g and r['slice'] == s), None)
            vals.append(float(hit['strict_success']) if hit else 0.0)
        ax.bar([p + (i - 1.5) * width for p in x], vals, width, label=g)
    ax.set_xticks(list(x)); ax.set_xticklabels(labels)
    ax.set_ylabel('evidence-constrained accuracy ($ac_1$)')
    ax.set_ylim(0, 1.05); ax.grid(axis='y', alpha=0.25); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT, format='pdf', bbox_inches='tight')
    print(OUT)


if __name__ == '__main__':
    main()
