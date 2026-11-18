"""Task B — matched-supervision baseline fairness experiments.

Design (same RDF graph, same 500 queries, same gold answers, same metric code
in every group):

  Group 1 NO_SUPERVISION      systems see only the query text + surface anchors.
  Group 2 MATCHED_SUPERVISION every system receives THE SAME alignment table
          (alias_index from build_llm_memory, coverage 0.92) — the same
          cross-lingual surface->URI mapping the LLM planner receives.
  Group 3 ORACLE              ground-truth gold URIs + equivalent traversal.
          UPPER BOUND ONLY, not a deployable baseline.

Systems per group: nonllm_localized (surface/aligned URI -> bounded traversal)
and oracle_traversal. LLM and dense/sparql variants are handled separately in
matched_supervision_full.py; this script isolates the traversal component with
strictly matched information so the decomposition in Task B is auditable.
"""
from __future__ import annotations
import json, sys, time
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd

SUB = Path(__file__).resolve().parents[2]
SRC = SUB / "upstream"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SUB / "experiments"))

from scalable_data import build_dataset, build_llm_memory, SEED  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from engine import CandidateAnchorMapper, infer_predicate_constraints, WORK_ATTR_PREDS, WORK_LINK_PREDS, local_name  # noqa: E402
from metrics import score  # noqa: E402
from rdflib import URIRef  # noqa: E402

OUT = SUB / "ICT_EXPRESS_PHASE1/baseline_fairness"
COVERAGE = 0.92
MEM_SEED = SEED + 3


@dataclass
class Res:
    ranked_uris: list
    triples: list = field(default_factory=list)
    scanned: int = 0
    t_surface_ms: float = 0.0
    t_llm_ms: float = 0.0
    t_traversal_ms: float = 0.0
    e2e_ms: float = 0.0


def alignment_lookup(knowledge, label_to_key, alias_index, anchors, mapper):
    """Resolve surface anchors to ALL URIs via the shared alignment table.

    This mirrors EXACTLY the LLM planner's information path:
      anchor label -> canonical key -> knowledge[key] (both languages)
      -> alias_index[form] -> all URIs in both graphs.
    Thus MATCHED_SUPERVISION gives non-LLM systems the same cross-graph
    mapping the LLM receives, no more and no less.
    """
    uris, seen, keys = [], set(), set()
    for a in anchors:
        key = mapper.normalize(a.label) if a.label else None
        canon = label_to_key.get(key) if key else None
        if canon is None or canon in keys:
            continue
        keys.add(canon)
        for form in knowledge.get(canon, []):
            for u, g in alias_index.get(form, ()):
                if u not in seen:
                    seen.add(u); uris.append(u)
    return uris


def traverse(graphs_by_uri, uris, constraints):
    triples, scanned = [], 0
    want_work = bool(constraints & WORK_ATTR_PREDS)
    for u in uris:
        entry = graphs_by_uri.get(u)
        if entry is None:
            continue
        g = entry[1]
        for s, p, o in g.triples((URIRef(u), None, None)):
            scanned += 1
            pl = local_name(p)
            if not constraints or pl in constraints:
                triples.append((str(s), str(p), str(o)))
            if want_work and pl in WORK_LINK_PREDS:
                for ws, wp, wo in g.triples((o, None, None)):
                    scanned += 1
                    if not constraints or local_name(wp) in constraints:
                        triples.append((str(ws), str(wp), str(wo)))
    return triples, scanned


def main():
    bundle = build_dataset(target_triples=50_000, seed=SEED)
    bench = build_benchmark(bundle)
    knowledge, label_to_key, alias_index, uri_graph = build_llm_memory(
        bundle, coverage=COVERAGE, seed=MEM_SEED)
    ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
                   "B": ["http://example.org/schemaB/alias"]}
    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)
    graphs_by_uri = {}
    for gname, g in bundle.graphs.items():
        for s in set(g.subjects()):
            graphs_by_uri.setdefault(str(s), (gname, g))
    total = bundle.total_triples

    rows = []
    for q in bench.queries:
        gold_uris = [str(u) for u in q.gt_uris]
        gold_vals = [str(v) for v in q.gt_values]
        anchors, examined = mapper.candidates(q.text)
        constraints = set(infer_predicate_constraints(q.text))
        aligned = alignment_lookup(knowledge, label_to_key, alias_index, anchors, mapper)
        exposed = any(u in aligned for u in gold_uris)

        surface_uris = [a.uri for a in anchors]
        groups = {
            "NO_SUPERVISION": surface_uris,                 # surface only
            "MATCHED_SUPERVISION": aligned,                 # shared alignment table
            "ORACLE": gold_uris,                            # upper bound
        }
        for group, uris in groups.items():
            t0 = time.perf_counter()
            triples, scanned = traverse(graphs_by_uri, uris, constraints)
            t1 = time.perf_counter()
            res = Res(ranked_uris=uris, triples=triples, scanned=scanned,
                      t_surface_ms=0.0, t_llm_ms=0.0,
                      t_traversal_ms=(t1-t0)*1000, e2e_ms=(t1-t0)*1000)
            m = score(res, gold_uris, gold_vals, total)
            m.update({"qid": q.qid, "group": group, "system": "localized_traversal",
                      "category": q.category, "exposed": exposed,
                      "n_anchors": len(anchors), "n_aligned": len(aligned),
                      "label_examined": examined})
            rows.append(m)

    t = pd.DataFrame(rows)
    t.to_csv(OUT / "MATCHED_SUPERVISION_RESULTS.csv", index=False)
    print(f"wrote {OUT/'MATCHED_SUPERVISION_RESULTS.csv'} rows={len(t)}")
    print(t.groupby(["group", "category"])[["hits1", "ac1", "vic"]].mean().round(4).to_string())
    print("\nBy exposure:")
    print(t.groupby(["group", "exposed"])[["hits1", "ac1"]].mean().round(4).to_string())

if __name__ == "__main__":
    main()
