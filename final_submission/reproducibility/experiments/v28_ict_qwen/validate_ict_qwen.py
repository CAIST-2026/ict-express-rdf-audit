"""Validate the retained 60-query Qwen ICT probe and downstream outcomes."""
import csv,json
from pathlib import Path
P=Path(__file__).resolve().parent
trace=[json.loads(x) for x in (P/'prompt_completion_trace.jsonl').open(encoding='utf-8') if x.strip()]
rows=list(csv.DictReader((P/'query_level_results.csv').open(encoding='utf-8')))
assert len(trace)==60 and len({r['qid'] for r in trace})==60
assert len(rows)==240
assert all(r['model'].startswith('qwen2.5:7b') for r in trace)
assert all(r['llm_output_valid']==1 and r['llm_selection_correct']==1 for r in trace)
assert all(r['prompt'] and r['completion'] for r in trace)
for selector in ('deterministic','qwen'):
    complete=[r for r in rows if r['selector']==selector and r['condition']=='complete_mapping']
    altered=[r for r in rows if r['selector']==selector and r['condition']=='missing_stale_mapping']
    assert len(complete)==len(altered)==60
    assert sum(int(r['target_exact']) for r in complete)==60
    assert sum(int(r['gold_context_retained']) for r in complete)==60
    assert sum(int(r['target_exact']) for r in altered)==30
    assert sum(int(r['context_lost']) for r in altered)==30
print(json.dumps({'calls':60,'valid_source_code_selections':60,'downstream_mapping_checks':120,'checks':'passed'}))
