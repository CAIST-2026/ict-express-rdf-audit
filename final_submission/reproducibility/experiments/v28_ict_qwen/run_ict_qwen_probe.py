"""Run Qwen2.5-7B as a candidate selector on the 60 synthetic ICT queries.
The query contains a generated asset code; this is a constrained selection probe,
not evidence of autonomous cross-lingual inference or operational performance.
"""
from __future__ import annotations
import csv,json,re,time
from datetime import datetime,timezone
from pathlib import Path
import requests
HERE=Path(__file__).resolve().parent
KG=HERE.parent/'v27_mini_ict'
MODEL='qwen2.5:7b'; SEED=20261120; HOST='http://localhost:11434'

def read_jsonl(path): return [json.loads(x) for x in path.open(encoding='utf-8') if x.strip()]
def main():
    manifest=json.loads((KG/'entity_manifest.json').read_text(encoding='utf-8'))
    queries=read_jsonl(KG/'queries.jsonl')
    mapping_data=json.loads((KG/'mapping_intervention.json').read_text(encoding='utf-8'))
    states=mapping_data['per_query_state']; corrupted=mapping_data['mapping']
    entities=manifest['records']; by_type={}
    for e in entities: by_type.setdefault(e['type'],[]).append(e)
    graph_path=KG/'mini_ict_bilingual_graph.ttl'
    from rdflib import Graph,URIRef
    g=Graph();g.parse(graph_path,format='turtle')
    trace_path=HERE/'prompt_completion_trace.jsonl'; result_path=HERE/'query_level_results.csv'
    rows=[]
    with trace_path.open('w',encoding='utf-8') as trace:
      for q in queries:
        candidates=[{'code':e['code'],'zh_label':e['zh_label'],'en_label':e['en_label']} for e in by_type[q['type']]]
        prompt=("You are selecting the source asset named in a bilingual ICT inventory query. "
          "Choose exactly one source entity from the candidate list. The query may ask about an associated alarm, affected service, or dependency; do not select a related object. "
          "Copy the candidate's code exactly. Return JSON only: {\"selected_code\":\"...\"}.\n"
          f"Query: {q['query']}\nCandidate source entities: {json.dumps(candidates,ensure_ascii=False)}")
        t0=time.perf_counter()
        response=requests.post(f'{HOST}/api/chat',json={'model':MODEL,'messages':[{'role':'user','content':prompt}],
          'stream':False,'format':'json','options':{'temperature':0,'num_predict':96}},timeout=300)
        response.raise_for_status(); payload=response.json(); completion=payload.get('message',{}).get('content','')
        elapsed=(time.perf_counter()-t0)*1000
        try: selected=str(json.loads(completion).get('selected_code','')).strip()
        except Exception: selected=''
        candidate_codes={e['code'] for e in by_type[q['type']]}
        valid=int(selected in candidate_codes); llm_select=int(valid and selected==q['code'])
        match=re.search(r'([A-Z_]+-\d{3})',q['query']); deterministic=match.group(1) if match else ''
        d_select=int(deterministic==q['code'])
        rec={'qid':q['qid'],'type':q['type'],'query':q['query'],'query_language':q['query_language'],
             'gold_source_code':q['code'],'llm_selected_code':selected,'llm_output_valid':valid,
             'llm_selection_correct':llm_select,'deterministic_selected_code':deterministic,
             'deterministic_selection_correct':d_select,'model':payload.get('model',MODEL),
             'temperature':0,'num_predict':96,'seed':SEED,'elapsed_ms':round(elapsed,1),
             'prompt':prompt,'completion':completion,'timestamp_utc':datetime.now(timezone.utc).isoformat()}
        trace.write(json.dumps(rec,ensure_ascii=False)+'\n');trace.flush()
        for selector,code,sel_correct in [('deterministic',deterministic,d_select),('qwen',selected,llm_select)]:
          source_uri=f'https://example.org/mini-ict/A/{q["type"]}/{code}' if code else ''
          for condition in ('complete_mapping','missing_stale_mapping'):
            if condition=='complete_mapping':
              target=f'https://example.org/mini-ict/B/{q["type"]}/{code}' if code else ''
            else: target=corrupted.get(source_uri,'')
            evidence=list(g.triples((URIRef(target),None,None))) if target else []
            exact=int(bool(target) and target==q['gold_target_uri'])
            ctx=int(exact and bool(evidence))
            rows.append({'qid':q['qid'],'type':q['type'],'selector':selector,'condition':condition,
              'mapping_state':'complete' if condition=='complete_mapping' else states[q['qid']],
              'selected_code':code,'selection_correct':sel_correct,'target_exact':exact,
              'gold_context_retained':ctx,'context_lost':int(not ctx),'gold_context_triples':6,
              'retrieved_context_triples':len(evidence)})
        print(f'{q["qid"]}: Qwen={selected!r} exact={llm_select} {elapsed:.0f} ms',flush=True)
    with result_path.open('w',newline='',encoding='utf-8') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'n_queries':len(queries),'n_llm_calls':len(queries),'model':MODEL,'seed':SEED,'synthetic':True,
      'llm_selection_correct':sum(int(json.loads(x)['llm_selection_correct']) for x in trace_path.open(encoding='utf-8')),
      'deterministic_selection_correct':sum(r['selection_correct'] for r in rows if r['selector']=='deterministic' and r['condition']=='complete_mapping'),
      'conditions':{}}
    for selector in ('deterministic','qwen'):
      summary['conditions'][selector]={}
      for cond in ('complete_mapping','missing_stale_mapping'):
        rr=[r for r in rows if r['selector']==selector and r['condition']==cond]
        summary['conditions'][selector][cond]={'n':len(rr),'selection_correct_n':sum(r['selection_correct'] for r in rr),
          'target_exact_n':sum(r['target_exact'] for r in rr),'context_retained_n':sum(r['gold_context_retained'] for r in rr),
          'context_loss_n':sum(r['context_lost'] for r in rr)}
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('SUMMARY',json.dumps(summary),flush=True)
if __name__=='__main__':main()
