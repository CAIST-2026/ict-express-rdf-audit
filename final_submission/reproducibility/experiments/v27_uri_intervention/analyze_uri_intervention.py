"""Recompute exact surface/key/identity outcomes from retained model completions."""
import csv, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
result=ROOT/'query_level_results.csv'; trace=ROOT/'prompt_completion_trace.jsonl'
rows=list(csv.DictReader(result.open(encoding='utf-8')))
records=[json.loads(x) for x in trace.open(encoding='utf-8') if x.strip()]
targets={(r['qid'],r['condition']):(r['target_entity_key'],r['target_surface_form']) for r in records}
for row in rows:
    qid=row['qid']
    for mode in ('full','uri_redacted','semantic_only'):
        key,label=targets[qid,mode]
        pred=row[f'{mode}_prediction'].strip().casefold()
        row['target_entity_key']=key
        row[f'{mode}_correct']=int(bool(pred) and pred==label.strip().casefold())
        row[f'{mode}_canonical_key_correct']=int(bool(pred) and pred==key.strip().casefold())
        row[f'{mode}_identity_correct']=int(bool(pred) and pred in {label.strip().casefold(),key.strip().casefold()})
fields=list(rows[0])
with result.open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
summary={'n':len(rows),'exposed_n':sum(int(r['original_gold_uri_exposed']) for r in rows),'unexposed_n':sum(1-int(r['original_gold_uri_exposed']) for r in rows),'conditions':{},'stratified':{}}
for mode in ('full','uri_redacted','semantic_only'):
    summary['conditions'][mode]={'exact_opposite_language_label':sum(int(r[f'{mode}_correct']) for r in rows),'exact_canonical_key':sum(int(r[f'{mode}_canonical_key_correct']) for r in rows),'identity_either_key_or_label':sum(int(r[f'{mode}_identity_correct']) for r in rows)}
for val,name in ((1,'exact_answer_uri_present'),(0,'exact_answer_uri_absent_other_cues_may_remain')):
    group=[r for r in rows if int(r['original_gold_uri_exposed'])==val]
    summary['stratified'][name]={'n':len(group),'conditions':{m:{'exact_opposite_language_label':sum(int(r[f'{m}_correct']) for r in group),'exact_canonical_key':sum(int(r[f'{m}_canonical_key_correct']) for r in group),'identity_either_key_or_label':sum(int(r[f'{m}_identity_correct']) for r in group)} for m in ('full','uri_redacted','semantic_only')}}
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
