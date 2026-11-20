"""Shared utilities for the Wikidata LLM vs deterministic comparison."""
from __future__ import annotations

import json
import re
from pathlib import Path

WIKI = 'http://www.wikidata.org/entity/'
BASE = Path(__file__).resolve().parents[1] / 'data' / 'wikidata' / 'source_inputs'
OUT = Path(__file__).resolve().parents[1]
QUERY_SET = BASE / 'queries' / 'WIKIDATA_QUERY_SET.csv'
ENTITIES = BASE / 'processed_data' / 'WIKIDATA_ENTITIES.json'
ATTRS = BASE / 'processed_data' / 'WIKIDATA_ATTRIBUTES.json'

FIELDS = [
    'qid', 'family', 'alignment_split', 'group', 'system',
    'query_type', 'query_text', 'subject_zh_label', 'subject_en_label',
    'gold_entity', 'gold_uri', 'gold_values',
    'alignment_entry_available', 'alignment_uri_in_input',
    'candidate_pool', 'prompt_version', 'model', 'seed',
    'predicted_uri', 'predicted_label', 'evidence_used',
    'hits1', 'mrr', 'strict_success', 'vic',
    'latency_ms', 'inference_ms', 'traversal_ms',
    'execution_status', 'error_message', 'gold_used_as_input',
    'timestamp',
]


def load_inputs():
    import csv
    with QUERY_SET.open(newline='', encoding='utf-8-sig') as f:
        queries = list(csv.DictReader(f))
    entities = json.loads(ENTITIES.read_text(encoding='utf-8'))
    attrs = json.loads(ATTRS.read_text(encoding='utf-8'))
    return queries, entities, attrs


def split_indices(entities):
    split = max(1, int(len(entities) * 0.7))
    return entities[:split], entities[split:]


def build_indices(entities, attrs):
    label_zh, label_en = {}, {}
    for e in entities:
        label_zh.setdefault(e['zh'], []).append(e['uri'])
        label_en.setdefault(e['en'], []).append(e['uri'])
    objects = {}
    for qid, props in attrs.items():
        uri = WIKI + qid
        vals = []
        for vs in props.values():
            vals.extend(WIKI + v for v in vs)
        vals.extend(e['zh'] for e in entities if e['uri'] == uri)
        vals.extend(e['en'] for e in entities if e['uri'] == uri)
        objects[uri] = vals
    for e in entities:
        objects.setdefault(e['uri'], [e['zh'], e['en']])
    return label_zh, label_en, objects


def gold_values_for(q):
    vals = [str(v) for v in json.loads(q['gold_values'])]
    norm = set(vals)
    norm.update(WIKI + v for v in vals if str(v).startswith('Q'))
    return vals, norm


def evaluate(uri, objects, gold_uri, gold_norm):
    evidence = set(objects.get(uri, [])) if uri else set()
    vic = float(any(v in evidence for v in gold_norm))
    rank0 = float(uri == gold_uri)
    return rank0, rank0, float(rank0 > 0 and vic > 0), vic, '|'.join(sorted(evidence))


def parse_json_object(text: str) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


def resolve_prediction(parsed, candidate_pool, label_index, alignment_map):
    uri = str(parsed.get('uri', '') or '').strip()
    label = str(parsed.get('candidate', '') or parsed.get('label', '') or '').strip()
    if uri and uri.startswith(WIKI):
        return uri, label
    if label in label_index:
        return label_index[label][0], label
    if uri in alignment_map.values():
        return uri, next((k for k, v in alignment_map.items() if v == uri), '')
    return '', label
