"""Structural checks for the saved three-condition URI intervention trace."""
import json,re
from collections import Counter,defaultdict
from pathlib import Path
P=Path(__file__).resolve().parent/'prompt_completion_trace.jsonl'
rows=[json.loads(x) for x in P.open(encoding='utf-8') if x.strip()]
assert len(rows)==180, f'expected 180 prompts, got {len(rows)}'
assert all(r['backend']=='ollama' and r['completion'] for r in rows), 'fallback/empty output present'
by=defaultdict(dict)
for r in rows:
    assert r['condition'] not in by[r['qid']], 'duplicate call'
    by[r['qid']][r['condition']]=r
assert len(by)==60 and all(set(x)=={'full','uri_redacted','semantic_only'} for x in by.values())
strata=Counter(int(r['original_gold_uri_exposed']) for r in rows if r['condition']=='full')
assert strata=={1:40,0:20},strata
for qid,conds in by.items():
    full=conds['full']
    assert (full['gold_uri'] in full['prompt_sent'])==bool(full['original_gold_uri_exposed'])
    for mode in ('uri_redacted','semantic_only'):
        sent=conds[mode]['prompt_sent']
        assert not re.search(r'https?://',sent), f'URI string remains: {qid}/{mode}'
        a,b,c='Candidate surface anchors (retrieved by string matching): ','\nCross-lingual entity profiles (canonical, all surface forms, all URIs across both graphs): ','\nPredicate schema (local name -> description): '
        i,j=sent.index(a)+len(a),sent.index(b);k=sent.index(b)+len(b);l=sent.index(c)
        anchors=json.loads(sent[i:j]); profiles=json.loads(sent[k:l])
        assert all('uri' not in x for x in anchors),f'anchor URI remains {qid}/{mode}'
        assert all(x.get('uris')==[] for x in profiles),f'profile URI remains {qid}/{mode}'
        if mode=='semantic_only':
            assert all('canonical' not in x for x in profiles),f'canonical key remains {qid}'
            assert all('graph' not in x and 'score' not in x for x in anchors)
print(json.dumps({'calls':len(rows),'queries':len(by),'strata':dict(strata),'checks':'passed'},indent=2))
