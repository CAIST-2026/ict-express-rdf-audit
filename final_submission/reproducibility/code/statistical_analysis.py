#!/usr/bin/env python3
"""Paired statistical analysis for the Wikidata LLM comparison."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import stats

from common import OUT

ROOT = OUT.parent
QPATH = ROOT / 'P1_Query_Level_Results.csv'
OUTPATH = ROOT / 'P1_Statistical_Analysis.csv'
RNG = np.random.default_rng(20261119)


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def slice_rows(rows, name):
    if name == 'ALL':
        return rows
    if name == 'one-hop':
        return [r for r in rows if r['family'] == 'one-hop']
    if name == 'cross-lingual':
        return [r for r in rows if r['family'] == 'cross-lingual']
    if name == 'cross_train':
        return [r for r in rows if r['family'] == 'cross-lingual' and r['alignment_split'] == 'train']
    if name == 'cross_heldout':
        return [r for r in rows if r['family'] == 'cross-lingual' and r['alignment_split'] == 'held-out']
    raise ValueError(name)


def paired_bootstrap_ci(a, b, reps=10000):
    d = a - b
    n = len(d)
    if n == 0:
        return float('nan'), float('nan')
    idx = RNG.integers(0, n, size=(reps, n))
    diffs = d[idx].mean(axis=1)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def main():
    rows = read(QPATH)
    by_group = {}
    for g in sorted({r['group'] for r in rows}):
        by_group[g] = {r['qid']: r for r in rows if r['group'] == g}

    contrasts = [
        ('llm_matched', 'deterministic_matched', 'ALL'),
        ('llm_matched', 'deterministic_matched', 'one-hop'),
        ('llm_matched', 'deterministic_matched', 'cross-lingual'),
        ('llm_matched', 'deterministic_matched', 'cross_train'),
        ('llm_matched', 'deterministic_matched', 'cross_heldout'),
        ('llm_no_alignment', 'deterministic_matched', 'cross-lingual'),
    ]
    out = []
    for a_group, b_group, sname in contrasts:
        base = slice_rows(list(by_group[a_group].values()), sname)
        qids = [r['qid'] for r in base]
        a = np.array([float(by_group[a_group][q]['strict_success']) for q in qids if q in by_group[b_group]])
        b = np.array([float(by_group[b_group][q]['strict_success']) for q in qids if q in by_group[b_group]])
        n01 = int(np.sum((a == 0) & (b == 1)))
        n10 = int(np.sum((a == 1) & (b == 0)))
        n_disc = n01 + n10
        p = float(stats.binomtest(min(n01, n10), n_disc, 0.5).pvalue) if n_disc else 1.0
        lo, hi = paired_bootstrap_ci(a, b)
        effect = float('inf') if n01 == 0 and n10 > 0 else (0.0 if n10 == 0 and n01 > 0 else
                       (n10 / n01 if n01 else float('nan')))
        out.append({
            'contrast': f'{a_group}_vs_{b_group}', 'slice': sname,
            'metric': 'strict_success', 'n_pairs': len(a), 'n_discordant': n_disc,
            'n01': n01, 'n10': n10,
            'mean_a': round(float(a.mean()), 6), 'mean_b': round(float(b.mean()), 6),
            'diff': round(float((a - b).mean()), 6),
            'diff_ci95_low_bootstrap': round(lo, 6),
            'diff_ci95_high_bootstrap': round(hi, 6),
            'mcnemar_exact_p_raw': round(p, 8),
            'effect_odds_ratio': effect if np.isfinite(effect) else 'inf',
            'note': 'zero discordance means equal observed outcomes, not equivalence',
        })
    ps = np.array([r['mcnemar_exact_p_raw'] for r in out])
    order = np.argsort(ps)
    adjusted = np.empty_like(ps)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (len(ps) - rank) * ps[idx]
        running = max(running, val)
        adjusted[idx] = min(1.0, running)
    for r, p_adj in zip(out, adjusted):
        r['mcnemar_exact_p_holm'] = round(float(p_adj), 8)

    with OUTPATH.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    (OUT/'results'/'statistical_tests.csv').write_bytes(OUTPATH.read_bytes())
    print(json.dumps({'contrasts': len(out), 'output': str(OUTPATH)}, indent=2))


if __name__ == '__main__':
    main()
