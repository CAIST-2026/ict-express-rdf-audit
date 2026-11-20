#!/usr/bin/env python3
"""Run Qwen2.5-7B on the authentic Wikidata benchmark.

Groups:
  llm_matched       : same train-pool alignment table as deterministic matched
  llm_no_alignment  : No explicit alignment table condition; query semantics
                      and candidate labels remain available

Gold answers and held-out gold URIs are never inserted into the prompt.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import datetime, timezone

import requests

from common import (FIELDS, OUT, build_indices, evaluate, gold_values_for,
                    load_inputs, parse_json_object, resolve_prediction,
                    split_indices)

MODEL = 'qwen2.5:7b'
PROMPT_VERSION = 'wikidata_llm_v1'
SEED = 20261119
URL = 'http://127.0.0.1:11434/api/chat'
SYSTEM = (
    'You are a conservative entity linker. Return only one JSON object. '
    'Choose exactly one candidate label or URI from the supplied evidence. '
    'Do not invent entities and do not explain.'
)


def build_prompt(q, candidate_pool, alignment_map, use_alignment):
    parts = [
        'Query: ' + q['text'],
        'Candidate labels (all from the allowed surface index): ' +
        json.dumps(candidate_pool, ensure_ascii=False),
    ]
    if use_alignment:
        parts.append('Train-pool alignment evidence (no held-out entries): ' +
                     json.dumps(alignment_map, ensure_ascii=False))
    parts.append(
        'Return JSON only: {"candidate": "<one label>", "uri": "<one URI or empty>"}. '
        'If alignment evidence contains the query subject, you may use its URI.'
    )
    return '\n'.join(parts)


def call_llm(prompt: str) -> tuple[str, float, str]:
    t0 = time.perf_counter()
    r = requests.post(URL, json={
        'model': MODEL,
        'stream': False,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': prompt},
        ],
        'options': {'temperature': 0, 'num_predict': 96},
    }, timeout=300)
    ms = (time.perf_counter() - t0) * 1000.0
    if r.status_code != 200:
        return '', ms, f'HTTP {r.status_code}: {r.text[:200]}'
    return r.json().get('message', {}).get('content', ''), ms, ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--group', choices=['llm_matched', 'llm_no_alignment'], required=True)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    queries, entities, attrs = load_inputs()
    train, _held = split_indices(entities)
    alignment_map = {e['zh']: e['uri'] for e in train}
    label_zh, label_en, objects = build_indices(entities, attrs)
    out_path = OUT / 'results' / f'raw_{args.group}.csv'
    done = set()
    if out_path.exists():
        with out_path.open(newline='', encoding='utf-8-sig') as f:
            done = {r['qid'] for r in csv.DictReader(f)}

    random.seed(SEED)
    with out_path.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not done and out_path.stat().st_size == 0:
            writer.writeheader()
        n = 0
        for q in queries:
            if q['qid'] in done:
                continue
            if args.limit and n >= args.limit:
                break
            is_cross = q['family'] == 'cross-lingual'
            candidate_pool = sorted(label_en if is_cross else label_zh)
            use_alignment = args.group == 'llm_matched' and is_cross
            prompt = build_prompt(q, candidate_pool, alignment_map, use_alignment)
            if q['alignment_split'] == 'held-out' and q['gold_uri'] in prompt:
                raise RuntimeError(f'held-out gold URI leaked into prompt for {q["qid"]}')
            if q['family'] == 'one-hop' and q['gold_values'] in prompt:
                raise RuntimeError(f'gold answer leaked into one-hop prompt for {q["qid"]}')

            content, latency_ms, error = call_llm(prompt)
            parsed = parse_json_object(content)
            label_index = label_en if is_cross else label_zh
            pred_uri, pred_label = resolve_prediction(parsed, candidate_pool,
                                                      label_index, alignment_map)
            gold_vals, gold_norm = gold_values_for(q)
            hits1, mrr, strict_success, vic, evidence = evaluate(
                pred_uri, objects, q['gold_uri'], gold_norm)
            row = {
                'qid': q['qid'], 'family': q['family'],
                'alignment_split': q['alignment_split'], 'group': args.group,
                'system': f'{MODEL}_{args.group}',
                'query_type': q['family'], 'query_text': q['text'],
                'subject_zh_label': q['zh_label'], 'subject_en_label': q['en_label'],
                'gold_entity': q['subject_qid'], 'gold_uri': q['gold_uri'],
                'gold_values': json.dumps(gold_vals, ensure_ascii=False),
                'alignment_entry_available': str(use_alignment and q['zh_label'] in alignment_map),
                'alignment_uri_in_input': str(alignment_map.get(q['zh_label'], '') if use_alignment else ''),
                'candidate_pool': '|'.join(candidate_pool), 'prompt_version': PROMPT_VERSION,
                'model': MODEL, 'seed': SEED,
                'predicted_uri': pred_uri, 'predicted_label': pred_label,
                'evidence_used': evidence,
                'hits1': hits1, 'mrr': mrr, 'strict_success': strict_success, 'vic': vic,
                'latency_ms': round(latency_ms, 3),
                'inference_ms': round(latency_ms, 3), 'traversal_ms': 0,
                'execution_status': 'ok' if not error else 'error',
                'error_message': error or content[:200] if error else '',
                'gold_used_as_input': 'false',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            writer.writerow(row)
            f.flush()
            n += 1
            print(f'{args.group} {n:03d} {q["qid"]} strict_success={strict_success} status={row["execution_status"]}', flush=True)


if __name__ == '__main__':
    main()
