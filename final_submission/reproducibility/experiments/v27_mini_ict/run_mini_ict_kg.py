"""Deterministic synthetic bilingual ICT KG probe; not operational/operator data."""
from __future__ import annotations
import csv, json, random
from pathlib import Path
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS
OUT=Path(__file__).resolve().parent
SEED=20261120
EX=Namespace('https://example.org/mini-ict/')

# Plausible but explicitly synthetic inventory records. Labels are generated from
# controlled templates; no operator, vendor, or production alarm logs are used.
DEVICES=[('router','路由器','Router'),('switch','交换机','Switch'),('base_station','基站','Base station'),('firewall','防火墙','Firewall'),('optical_terminal','光网络终端','Optical network terminal')]
ALARMS=[('link_down','链路中断','Link down'),('high_cpu','CPU过载','High CPU'),('signal_loss','信号丢失','Signal loss'),('temperature','温度过高','High temperature'),('auth_failure','认证失败','Authentication failure')]
SERVICES=[('voice','语音服务','Voice service'),('broadband','宽带接入','Broadband access'),('mobile_data','移动数据','Mobile data'),('vpn','企业VPN','Enterprise VPN'),('iot','物联网接入','IoT access')]

def main():
    rng=random.Random(SEED); g=Graph(); g.bind('ex',EX)
    records=[]
    types=[('device',DEVICES),('alarm',ALARMS),('service',SERVICES)]
    for typ, rows in types:
        for i in range(20):
            code=f'{typ.upper()}-{i+1:03d}'; root=rows[i%len(rows)]
            zh=f'{root[1]} {code}'; en=f'{root[2]} {code}'
            a=EX[f'A/{typ}/{code}']; b=EX[f'B/{typ}/{code}']
            for u,label,lang in ((a,zh,'zh'),(b,en,'en')):
                g.add((u,RDF.type,EX[typ.capitalize()]));g.add((u,RDFS.label,Literal(label,lang=lang)))
                g.add((u,EX.assetCode,Literal(code)))
            # Target-side contextual facts. Relationship pattern differs per domain.
            for j in range(3):
                other_type, other_rows=types[(types.index((typ,rows))+j+1)%3]
                other_code=f'{other_type.upper()}-{(i*3+j)%20+1:03d}'
                other=EX[f'B/{other_type}/{other_code}']
                pred={'device':EX.hasAlarm,'alarm':EX.affectsService,'service':EX.dependsOn}[typ]
                g.add((b,pred,other))
            records.append({'type':typ,'code':code,'zh_label':zh,'en_label':en,'source_uri':str(a),'target_uri':str(b)})
    # 540 triples: 60 paired entities x (two typed labels + code + three relations).
    g.serialize(OUT/'mini_ict_bilingual_graph.ttl',format='turtle')
    (OUT/'entity_manifest.json').write_text(json.dumps({'synthetic':True,'seed':SEED,'records':records,'triple_count':len(g),'note':'Generated controlled inventory entities; not collected from an operator or deployed ICT system.'},ensure_ascii=False,indent=2),encoding='utf-8')
    by={(r['type'],r['code']):r for r in records}
    queries=[]
    for typ,rows in types:
        for i in range(20):
            ent=by[(typ,f'{typ.upper()}-{i+1:03d}')]
            zh_to_en=(i%2==0)
            label=ent['zh_label'] if zh_to_en else ent['en_label']
            ask='查询关联告警' if typ=='device' else ('查询影响的服务' if typ=='alarm' else '查询依赖对象')
            ask_en='find associated alarms' if typ=='device' else ('find affected services' if typ=='alarm' else 'find dependencies')
            query=f'{label}：{ask}' if zh_to_en else f'{label}: {ask_en}'
            queries.append({'qid':f'I{len(queries)+1:03d}','type':typ,'code':ent['code'],'query':query,'query_language':'zh' if zh_to_en else 'en','source_uri':ent['source_uri'],'gold_target_uri':ent['target_uri']})
    (OUT/'queries.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in queries),encoding='utf-8')
    # Mapping states: all complete; 10/20 missing; 10/20 stale in each domain.
    states={}
    for typ,rows in types:
        domain=[q for q in queries if q['type']==typ]
        order=list(domain);rng.shuffle(order)
        for idx,q in enumerate(order):
            if idx<5: states[q['qid']]='missing'
            elif idx<10: states[q['qid']]='stale'
            else: states[q['qid']]='complete'
    maps={q['source_uri']:q['gold_target_uri'] for q in queries}
    # Stale keys redirect deterministically to the next inventory URI of same type.
    for typ,rows in types:
        domain=[q for q in queries if q['type']==typ]
        for q in domain:
            if states[q['qid']]=='stale':
                nextq=domain[(int(q['code'].split('-')[1])%20)]
                if nextq['gold_target_uri']==q['gold_target_uri']: nextq=domain[(int(q['code'].split('-')[1])+1)%20]
                maps[q['source_uri']]=nextq['gold_target_uri']
            elif states[q['qid']]=='missing': maps.pop(q['source_uri'],None)
    (OUT/'mapping_intervention.json').write_text(json.dumps({'seed':SEED,'complete_mapping':'gold source-to-target links for all queries','intervention':'for each type, 5 mappings removed, 5 redirected to a different same-type target, and 10 kept correct','per_query_state':states,'mapping':maps},indent=2),encoding='utf-8')
    rows=[]
    for q in queries:
        for condition in ('complete_mapping','missing_stale_mapping'):
            target=(q['gold_target_uri'] if condition=='complete_mapping' else maps.get(q['source_uri']))
            # Surface lookup is exact on bilingual labels; retrieval requires a valid cross-graph map.
            evidence=[] if target is None else list(g.triples((URIRef(target),None,None)))
            gold_evidence=list(g.triples((URIRef(q['gold_target_uri']),None,None)))
            correct=int(target==q['gold_target_uri'])
            grounded=int(correct and bool(evidence) and len(evidence)>=1)
            lost=int(not correct or not evidence)
            rows.append({'qid':q['qid'],'type':q['type'],'query':q['query'],'condition':condition,'mapping_state':'complete' if condition=='complete_mapping' else states[q['qid']], 'gold_target_uri':q['gold_target_uri'],'retrieved_target_uri':str(target or ''),'exact_target':correct,'gold_context_triples':len(gold_evidence),'retrieved_context_triples':len(evidence),'gold_context_retained':grounded,'context_lost':lost})
    with (OUT/'query_level_results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={}
    for cond in ('complete_mapping','missing_stale_mapping'):
        rr=[r for r in rows if r['condition']==cond]
        summary[cond]={'n':len(rr),'exact_target_n':sum(r['exact_target'] for r in rr),'exact_target_rate':sum(r['exact_target'] for r in rr)/len(rr),'context_lost_n':sum(r['context_lost'] for r in rr),'context_loss_rate':sum(r['context_lost'] for r in rr)/len(rr),'mean_gold_context_triples':sum(r['gold_context_triples'] for r in rr)/len(rr),'mean_retrieved_context_triples':sum(r['retrieved_context_triples'] for r in rr)/len(rr)}
    summary.update({'queries':len(queries),'triples':len(g),'seed':SEED,'synthetic':True})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text('# Mini ICT KG experiment\n\nThis is a deterministic, synthetic proof-of-concept generated from controlled Chinese/English device, alarm, and service labels. It is not real operator, vendor, or field data and does not estimate deployment performance. The 60 bilingual queries are evaluated against the same graph under complete mappings and under an intervention that removes or redirects mappings. The script, seed, graph, entity manifest, mappings, query set, and query-level outcomes are retained.\n\nRun: `python3 run_mini_ict_kg.py` (requires rdflib).\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
