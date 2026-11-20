"""Three-arm, stratified URI/canonical-key intervention for the cross-lingual query pool.
All prompts/completions are appended as JSONL immediately after each successful call.
"""
from __future__ import annotations
import csv, json, random, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'reproducibility'/'code'))
from scalable_data import build_dataset, build_llm_memory
from scalable_benchmark import build_benchmark
from engine import CandidateAnchorMapper, OllamaLLMFilter, schema_summary

EXP = ROOT/'reproducibility/data/main/prompt_exposure_recomputed.csv'
OUT = Path(__file__).resolve().parent
SEEDS = {'data':20260101, 'benchmark':20260102, 'memory':20260104, 'sample':20261120}
N_EXPOSED, N_UNEXPOSED = 40, 20
MODEL='qwen2.5:7b'

class Capture:
    def __init__(self, mode): self.mode=mode; self.last=None
    @staticmethod
    def sections(prompt):
        a='Candidate surface anchors (retrieved by string matching): '
        b='\nCross-lingual entity profiles (canonical, all surface forms, all URIs across both graphs): '
        c='\nPredicate schema (local name -> description): '
        i,j,k=prompt.index(a)+len(a),prompt.index(b),prompt.index(b)+len(b)
        l=prompt.index(c)
        anchors=json.loads(prompt[i:j]); profiles=json.loads(prompt[k:l])
        return (a,b,c,i,j,k,l,anchors,profiles)
    def post(self,url,json:dict,**kwargs):
        body=json.copy(); prompt=body['messages'][0]['content']
        a,b,c,i,j,k,l,anchors,profiles=self.sections(prompt)
        if self.mode!='full':
            for x in anchors:
                x.pop('uri',None)
                if self.mode=='semantic_only': x.pop('graph',None); x.pop('score',None)
            for x in profiles:
                if self.mode=='semantic_only': x.pop('canonical',None)
                x['uris']=[]
        aa=__import__('json').dumps(anchors,ensure_ascii=False); pp=__import__('json').dumps(profiles,ensure_ascii=False)
        tail=prompt.index('Return STRICT JSON only')
        output_schema=("Return STRICT JSON only with keys: target_surface_form (string), predicate_constraints (array), and rationale (string). Select the candidate entity that matches the user query. Copy exactly one opposite-language surface form from the candidate profiles as target_surface_form. If no supported opposite-language form is available, return an empty string. Do not output canonical keys or URIs as the target_surface_form.")
        sent=prompt[:i]+aa+prompt[j:k]+pp+prompt[l:tail]+output_schema
        body['messages']=[dict(body['messages'][0],content=sent)]
        t=time.perf_counter(); resp=requests.post(url,json=body,**kwargs); elapsed=(time.perf_counter()-t)*1000
        resp.raise_for_status(); data=resp.json(); content=data.get('message',{}).get('content','')
        self.last={'original':prompt,'sent':sent,'completion':content,'elapsed_ms':elapsed,
                   'model':data.get('model',MODEL),'done_reason':data.get('done_reason','')}
        return resp

def norm(s): return ' '.join(str(s).casefold().split())
def parse_target(s):
    try:
        d=json.loads(s); return str(d.get('target_surface_form','')).strip()
    except Exception:
        m=re.search(r'"target_surface_form"\s*:\s*"([^"]*)"',s)
        return m.group(1).strip() if m else ''

def main():
    bundle=build_dataset(50_000,seed=SEEDS['data'])
    bench=build_benchmark(bundle,n_1hop=200,n_2hop=150,n_cross=150,seed=SEEDS['benchmark'])
    knowledge,label_to_key,alias_index,_=build_llm_memory(bundle,coverage=.92,seed=SEEDS['memory'])
    mapper=CandidateAnchorMapper(bundle.graphs,{'A':['http://example.org/schemaA/别名'],'B':['http://example.org/schemaB/alias']})
    schema=schema_summary(bundle.graphs); qb={q.qid:q for q in bench.queries}
    with EXP.open(encoding='utf-8-sig',newline='') as f: exp=list(csv.DictReader(f))
    cross=[r for r in exp if r['category']=='cross-lingual']
    exposed=sorted(r['qid'] for r in cross if r['exposed']=='1')
    hidden=sorted(r['qid'] for r in cross if r['exposed']=='0')
    rng=random.Random(SEEDS['sample'])
    chosen=sorted(rng.sample(exposed,N_EXPOSED)+rng.sample(hidden,N_UNEXPOSED))
    (OUT/'sample_manifest.json').write_text(json.dumps({'seed':SEEDS['sample'],'n':len(chosen),'strata':{'exact_answer_uri_present':N_EXPOSED,'exact_answer_uri_absent_other_cues_may_remain':N_UNEXPOSED},'qids':chosen,'exact_answer_uri_absent_pool_size':len(hidden),'note':'Absence refers only to the exact answer-bearing URI string; counterpart URIs or canonical keys may remain in the original prompt.','conditions':['full','uri_redacted','semantic_only'],'model':MODEL,'temperature':0,'num_predict':256,'dataset_seeds':SEEDS},indent=2),encoding='utf-8')
    snap=OUT/'prompt_completion_trace.jsonl'; result=OUT/'query_level_results.csv'
    rows=[]
    for qid in chosen:
        q=qb[qid]
        # Cross-language target surface is the label in the graph opposite the query anchor.
        entities={e.key:e for e in bundle.entities}; entity=entities[q.entity_key]
        target=entity.en_label if q.lang=='zh' else entity.zh_label
        arms={}
        for mode in ('full','uri_redacted','semantic_only'):
            llm=OllamaLLMFilter(model=MODEL,entity_vocab=mapper.index,knowledge=knowledge,label_to_key=label_to_key,alias_index=alias_index,num_predict=256)
            cap=Capture(mode); llm.requests=cap
            anchors,_=mapper.candidates(q.text)
            plan=llm.make_plan(q.text,anchors,schema,{'category':q.category})
            rec=cap.last
            if not rec or not rec['completion'] or plan.backend!='ollama':
                raise RuntimeError(f'Invalid model record for {qid}/{mode}: backend={plan.backend}')
            pred=parse_target(rec['completion'])
            exact=norm(pred)==norm(target)
            arms[mode]={'prediction':pred,'target_surface_form':target,'correct':int(exact),'elapsed_ms':round(rec['elapsed_ms'],1)}
            trace={'qid':qid,'category':q.category,'query_language':q.lang,'condition':mode,'target_surface_form':target,
                   'target_entity_key':q.entity_key,'gold_uri':q.gt_uris[0],'model':rec['model'],'temperature':0,'num_predict':256,
                   'data_seed':SEEDS['data'],'benchmark_seed':SEEDS['benchmark'],'memory_seed':SEEDS['memory'],'sample_seed':SEEDS['sample'],
                   'prompt_original':rec['original'],'prompt_sent':rec['sent'],'completion':rec['completion'],
                   'exact_surface_match':int(exact),'original_gold_uri_exposed':int(qid in exposed),'backend':plan.backend,'done_reason':rec['done_reason'],
                   'timestamp_utc':datetime.now(timezone.utc).isoformat()}
            with snap.open('a',encoding='utf-8') as f: f.write(json.dumps(trace,ensure_ascii=False)+'\n')
            print(f'{qid} {mode}: exact={int(exact)} target={target!r} pred={pred!r} {rec["elapsed_ms"]:.0f}ms',flush=True)
        rows.append({'qid':qid,'original_gold_uri_exposed':int(qid in exposed),'target_surface_form':target,
                     **{f'{m}_prediction':arms[m]['prediction'] for m in arms},
                     **{f'{m}_correct':arms[m]['correct'] for m in arms},
                     **{f'{m}_canonical_key_correct':int(norm(arms[m]['prediction'])==norm(q.entity_key)) for m in arms},
                     **{f'{m}_identity_correct':int(norm(arms[m]['prediction']) in {norm(q.entity_key),norm(target)}) for m in arms},
                     **{f'{m}_elapsed_ms':arms[m]['elapsed_ms'] for m in arms}})
        with result.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'n':len(rows),'exposed_n':sum(r['original_gold_uri_exposed'] for r in rows),'unexposed_n':len(rows)-sum(r['original_gold_uri_exposed'] for r in rows),'conditions':{}}
    for mode in ('full','uri_redacted','semantic_only'):
        summary['conditions'][mode]={'exact_opposite_language_label':sum(r[f'{mode}_correct'] for r in rows),'exact_canonical_key':sum(r[f'{mode}_canonical_key_correct'] for r in rows),'identity_either_key_or_label':sum(r[f'{mode}_identity_correct'] for r in rows)}
    summary['stratified']={}
    for exposed_value,label in ((1,'exact_answer_uri_present'),(0,'exact_answer_uri_absent_other_cues_may_remain')):
        group=[r for r in rows if r['original_gold_uri_exposed']==exposed_value]
        summary['stratified'][label]={'n':len(group),'conditions':{m:{'exact_opposite_language_label':sum(r[f'{m}_correct'] for r in group),'exact_canonical_key':sum(r[f'{m}_canonical_key_correct'] for r in group),'identity_either_key_or_label':sum(r[f'{m}_identity_correct'] for r in group)} for m in ('full','uri_redacted','semantic_only')}}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('SUMMARY',json.dumps(summary),flush=True)
if __name__=='__main__': main()
