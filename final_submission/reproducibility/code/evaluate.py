#!/usr/bin/env python3
"""Aggregate Wikidata comparison results from query-level records."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

from common import FIELDS, OUT

ROOT = OUT.parent
RAW = sorted((OUT / 'results').glob('raw_*.csv'))


def read(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def cp_ci(k, n):
    if n == 0:
        return float('nan'), float('nan')
    lo = 0.0 if k == 0 else float(stats.beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(0.975, k + 1, n - k))
    return lo, hi


def main():
    rows = []
    for p in RAW:
        rows.extend(read(p))
    qpath = ROOT / 'P1_Query_Level_Results.csv'
    with qpath.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)

    agg = []
    lat = []
    slices = [('ALL', lambda r: True),
              ('one-hop', lambda r: r['family'] == 'one-hop'),
              ('cross-lingual', lambda r: r['family'] == 'cross-lingual'),
              ('cross_train', lambda r: r['family'] == 'cross-lingual' and r['alignment_split'] == 'train'),
              ('cross_heldout', lambda r: r['family'] == 'cross-lingual' and r['alignment_split'] == 'held-out')]
    for group in sorted({r['group'] for r in rows}):
        for sname, pred in slices:
            g = [r for r in rows if r['group'] == group and pred(r)]
            if not g:
                continue
            n = len(g)
            strict_success = np.array([float(r['strict_success']) for r in g])
            vic = np.array([float(r['vic']) for r in g])
            hits = np.array([float(r['hits1']) for r in g])
            k = int(strict_success.sum())
            lo, hi = cp_ci(k, n)
            ms = np.array([float(r['latency_ms']) for r in g if r['latency_ms']])
            agg.append({
                'group': group, 'slice': sname, 'n': n,
                'strict_success': round(float(strict_success.mean()), 6), 'strict_successes': k,
                'strict_ci95_low': round(lo, 6), 'strict_ci95_high': round(hi, 6),
                'vic': round(float(vic.mean()), 6), 'hits1': round(float(hits.mean()), 6),
            })
            if len(ms):
                se = float(np.std(ms, ddof=1)) / math.sqrt(len(ms)) if len(ms) > 1 else 0
                ci = stats.t.interval(0.95, len(ms)-1, loc=float(np.mean(ms)), scale=se) if len(ms) > 1 else (np.nan, np.nan)
                lat.append({
                    'group': group, 'slice': sname, 'n': len(ms),
                    'mean_ms': round(float(np.mean(ms)), 3),
                    'median_ms': round(float(np.median(ms)), 3),
                    'sd_ms': round(float(np.std(ms, ddof=1)), 3),
                    'p95_ms': round(float(np.percentile(ms, 95)), 3),
                    'ci95_low_ms': round(float(ci[0]), 3),
                    'ci95_high_ms': round(float(ci[1]), 3),
                })
    apath = ROOT / 'P1_Aggregate_Results.csv'
    lpath = ROOT / 'P1_Latency_Results.csv'
    for path, data in [(apath, agg), (lpath, lat)]:
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader(); w.writerows(data)
    for src, dst in [(apath, OUT/'results'/'aggregate_metrics.csv'),
                     (lpath, OUT/'results'/'latency_results.csv'),
                     (qpath, OUT/'results'/'query_level_results.csv')]:
        dst.write_bytes(src.read_bytes())
    print(json.dumps({'query_rows': len(rows), 'aggregate_rows': len(agg),
                      'latency_rows': len(lat), 'outputs': [str(qpath), str(apath), str(lpath)]}, indent=2))


if __name__ == '__main__':
    main()
