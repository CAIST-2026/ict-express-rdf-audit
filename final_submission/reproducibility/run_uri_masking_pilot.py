"""Paired 12-query URI-profile masking pilot; exploratory, not a new benchmark."""
from __future__ import annotations
import csv, json, json as jsonlib, random, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reproducibility'/'code'))
from scalable_data import build_dataset, build_llm_memory
from scalable_benchmark import build_benchmark
from engine import CandidateAnchorMapper, OllamaLLMFilter, schema_summary
PAT=re.compile(r'(Cross-lingual entity profiles \(canonical, all surface forms, all URIs across both graphs\): )(.*?)(\nPredicate schema \(local name -> description\): )',re.S)
class CaptureClient:
 def __init__(self, redacted): self.redacted=redacted; self.last=None
 def post(self,url,json,**kwargs):
  body=json.copy(); original=body['messages'][0]['content']; sent=original
  if self.redacted:
   m=PAT.search(original)
   if not m: raise RuntimeError('Could not locate candidate profile JSON')
   profiles=jsonlib.loads(m.group(2))
   for p in profiles: p['uris']=[]
   profile_json=jsonlib.dumps(profiles,ensure_ascii=False)
   sent=original[:m.start(2)]+profile_json+original[m.end(2):]
   body['messages']=[dict(body['messages'][0],content=sent)]
  t=time.perf_counter(); resp=requests.post(url,json=body,**kwargs); elapsed=(time.perf_counter()-t)*1000
  resp.raise_for_status(); data=resp.json()
  self.last={'original':original,'sent':sent,'completion':data.get('message',{}).get('content',''),
   'elapsed_ms':elapsed,'model':data.get('model','qwen2.5:7b'),'done_reason':data.get('done_reason','')}
  return resp

def main():
 data_seed,bench_seed,memory_seed=20260101,20260102,20260104
 bundle=build_dataset(50_000,seed=data_seed)
 bench=build_benchmark(bundle,n_1hop=200,n_2hop=150,n_cross=150,seed=bench_seed)
 knowledge,label_to_key,alias_index,_=build_llm_memory(bundle,coverage=.92,seed=memory_seed)
 mapper=CandidateAnchorMapper(bundle.graphs,{'A':['http://example.org/schemaA/别名'],'B':['http://example.org/schemaB/alias']})
 schema=schema_summary(bundle.graphs); q_by_id={q.qid:q for q in bench.queries}
 import pandas as pd
 exp=pd.read_csv(ROOT/'reproducibility/data/main/prompt_exposure_recomputed.csv')
 ids=sorted(exp[(exp.category=='cross-lingual')&(exp.exposed==1)].qid.astype(str))
 sample=sorted(random.Random(20261120).sample(ids,12))
 rows=[]; snapshots=[]
 for qid in sample:
  q=q_by_id[qid]; anchors,_=mapper.candidates(q.text); arms=[]
  for mode,redacted in [('full_profile',False),('profile_uri_redacted',True)]:
   llm=OllamaLLMFilter(model='qwen2.5:7b',entity_vocab=mapper.index,knowledge=knowledge,
    label_to_key=label_to_key,alias_index=alias_index,num_predict=256)
   client=CaptureClient(redacted); llm.requests=client
   plan=llm.make_plan(q.text,anchors,schema,{'category':q.category}); raw=client.last
   if raw is None or not raw['completion'] or plan.backend!='ollama':
    raise RuntimeError(f'No genuine completion for {qid}/{mode}; backend={plan.backend}')
   gold=str(q.gt_uris[0]); pred=str(plan.canonical_entity).strip(); top=plan.aligned_uris[0] if plan.aligned_uris else ''
   arm={'canonical_prediction':pred,'canonical_correct':int(pred==str(q.entity_key)),
    'top_uri_is_gold':int(top==gold),'gold_uri_exposed':int(gold in raw['sent']),
    'elapsed_ms':raw['elapsed_ms']}; arms.append(arm)
   snapshots.append({'qid':qid,'category':q.category,'condition':mode,'target_canonical':q.entity_key,
    'target_gold_uri':gold,'model':raw['model'],'temperature':0,'num_predict':256,
    'data_seed':data_seed,'benchmark_seed':bench_seed,'memory_seed':memory_seed,
    'sample_seed':20261120,'prompt_original':raw['original'],'prompt_sent':raw['sent'],
    'completion':raw['completion'],'backend':plan.backend,'gold_uri_exposed':arm['gold_uri_exposed'],
    'timestamp_utc':datetime.now(timezone.utc).isoformat()})
   print(f'{qid} {mode}: canonical={arm["canonical_correct"]}, top_uri={arm["top_uri_is_gold"]}, exposed={arm["gold_uri_exposed"]}, {arm["elapsed_ms"]:.0f} ms',flush=True)
  rows.append({'qid':qid,'target_canonical':q.entity_key,'gold_uri':q.gt_uris[0],
   'full_profile_canonical_correct':arms[0]['canonical_correct'],
   'redacted_profile_canonical_correct':arms[1]['canonical_correct'],
   'full_profile_top_uri_is_gold':arms[0]['top_uri_is_gold'],
   'redacted_profile_top_uri_is_gold':arms[1]['top_uri_is_gold'],
   'full_profile_gold_uri_exposed':arms[0]['gold_uri_exposed'],
   'redacted_profile_gold_uri_exposed':arms[1]['gold_uri_exposed'],
   'full_profile_elapsed_ms':round(arms[0]['elapsed_ms'],1),
   'redacted_profile_elapsed_ms':round(arms[1]['elapsed_ms'],1),
   'full_profile_canonical_prediction':arms[0]['canonical_prediction'],
   'redacted_profile_canonical_prediction':arms[1]['canonical_prediction']})
 out=ROOT/'reproducibility'/'data'/'main'
 with (out/'uri_masking_pilot.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with (out/'uri_masking_pilot_prompt_snapshots.jsonl').open('w',encoding='utf-8') as f:
  for r in snapshots:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 print('SUMMARY',json.dumps({'n':len(rows),
  'full_canonical_correct':sum(r['full_profile_canonical_correct'] for r in rows),
  'redacted_canonical_correct':sum(r['redacted_profile_canonical_correct'] for r in rows),
  'full_top_uri_gold':sum(r['full_profile_top_uri_is_gold'] for r in rows),
  'redacted_top_uri_gold':sum(r['redacted_profile_top_uri_is_gold'] for r in rows),
  'full_gold_exposed':sum(r['full_profile_gold_uri_exposed'] for r in rows),
  'redacted_gold_exposed':sum(r['redacted_profile_gold_uri_exposed'] for r in rows),
  'full_only_canonical':sum(r['full_profile_canonical_correct'] and not r['redacted_profile_canonical_correct'] for r in rows),
  'redacted_only_canonical':sum(r['redacted_profile_canonical_correct'] and not r['full_profile_canonical_correct'] for r in rows)},ensure_ascii=False))
if __name__=='__main__':main()
