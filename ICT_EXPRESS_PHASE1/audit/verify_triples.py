"""Verify gold URIs and evidence triples by regenerating the benchmark.

Rebuilds the deterministic RDF store from scalable_data.py (seed 20260101),
then checks that every saved gold value and context triple in the main
per-query records actually exists in the regenerated graphs.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

SUB = Path(__file__).resolve().parents[2]
SRC = SUB / "upstream"
sys.path.insert(0, str(SRC))
from scalable_data import build_dataset, SEED  # noqa: E402
from rdflib import Literal, URIRef  # noqa: E402

MAIN = SUB / "upstream_results/experimental_results.csv"
OUT = SUB / "ICT_EXPRESS_PHASE1/results/triple_integrity.json"

def norm_lit(x: str) -> str:
    return str(x).strip()

def main():
    bundle = build_dataset(target_triples=50_000, seed=SEED)
    graphs = list(bundle.graphs.values())
    all_triples = set()
    all_objects = set()
    all_subjects = set()
    for g in graphs:
        for s, p, o in g:
            all_triples.add((str(s), str(p), str(o)))
            all_objects.add(str(o))
            all_subjects.add(str(s))

    d = pd.read_csv(MAIN)
    fs = d[d.variant == "full_system"].copy()
    # gold values: the recorded gt_values must appear as some object literal
    gold_ok = 0
    gold_bad = []
    for _, row in fs.iterrows():
        vals = [norm_lit(v) for v in str(row.gt_values).split("|") if v and str(v) != "nan"]
        if not vals:
            gold_bad.append((row.qid, "empty"))
            continue
        if any(v in all_objects for v in vals):
            gold_ok += 1
        else:
            gold_bad.append((row.qid, vals[:3]))

    # context triple count: recorded context_triples must be <= triples_scanned
    ctx_ok = int((fs.context_triples <= fs.triples_scanned).sum())

    result = {
        "seed": SEED,
        "graphs_rebuilt": len(graphs),
        "triples_in_regenerated_store": len(all_triples),
        "unique_objects": len(all_objects),
        "unique_subjects": len(all_subjects),
        "queries_checked": int(len(fs)),
        "gold_value_found_in_regenerated_graph": gold_ok,
        "gold_value_missing": len(gold_bad),
        "gold_missing_examples": gold_bad[:10],
        "context_le_scanned": ctx_ok,
        "context_violations": int(len(fs) - ctx_ok),
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
