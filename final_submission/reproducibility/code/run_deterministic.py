#!/usr/bin/env python3
"""Run deterministic matched and oracle conditions on the Wikidata benchmark."""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone

from common import (FIELDS, OUT, build_indices, evaluate, gold_values_for,
                    load_inputs, split_indices)

PROMPT_VERSION = 'deterministic_v1'


def main():
    queries, entities, attrs = load_inputs()
    train, _held = split_indices(entities)
    alignment_map = {e['zh']: e['uri'] for e in train}
    label_zh, label_en, objects = build_indices(entities, attrs)
    out_path = OUT / 'results' / 'raw_deterministic_and_oracle.csv'
    rows = []
    for group in ('deterministic_matched', 'oracle'):
        for q in queries:
            is_cross = q['family'] == 'cross-lingual'
            candidate_pool = sorted(label_en if is_cross else label_zh)
            gold_vals, gold_norm = gold_values_for(q)
            t0 = time.perf_counter()
            ranked = []
            if group == 'oracle':
                ranked = [q['gold_uri']]
            else:
                if is_cross and q['zh_label'] in alignment_map:
                    ranked.append(alignment_map[q['zh_label']])
                target = label_en if is_cross else label_zh
                ranked.extend(u for u in target.get(q['zh_label'], []) if u not in ranked)
            pred_uri = ranked[0] if ranked else ''
            ms = (time.perf_counter() - t0) * 1000.0
            hits1, mrr, strict_success, vic, evidence = evaluate(
                pred_uri, objects, q['gold_uri'], gold_norm)
            rows.append({
                'qid': q['qid'], 'family': q['family'],
                'alignment_split': q['alignment_split'], 'group': group,
                'system': 'local_surface_alignment',
                'query_type': q['family'], 'query_text': q['text'],
                'subject_zh_label': q['zh_label'], 'subject_en_label': q['en_label'],
                'gold_entity': q['subject_qid'], 'gold_uri': q['gold_uri'],
                'gold_values': json.dumps(gold_vals, ensure_ascii=False),
                'alignment_entry_available': str(is_cross and q['zh_label'] in alignment_map)
                    if group == 'deterministic_matched' else 'false',
                'alignment_uri_in_input': str(alignment_map.get(q['zh_label'], ''))
                    if group == 'deterministic_matched' and is_cross else '',
                'candidate_pool': '|'.join(candidate_pool),
                'prompt_version': PROMPT_VERSION, 'model': 'deterministic', 'seed': 20261119,
                'predicted_uri': pred_uri,
                'predicted_label': q['en_label'] if is_cross else q['zh_label'],
                'evidence_used': evidence,
                'hits1': hits1, 'mrr': mrr, 'strict_success': strict_success, 'vic': vic,
                'latency_ms': round(ms, 6), 'inference_ms': 0,
                'traversal_ms': round(ms, 6),
                'execution_status': 'ok', 'error_message': '',
                'gold_used_as_input': 'true' if group == 'oracle' else 'false',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })
    with out_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
    print(f'wrote {len(rows)} rows to {out_path}')


if __name__ == '__main__':
    main()
