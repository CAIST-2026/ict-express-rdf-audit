"""Task C — real-world experiments on a LOCAL rdflib graph built from
authentic Wikidata SPARQL responses (RAW_SPARQL_RESPONSES.json).

Why local: the public WDQS endpoint aggressively rate-limits to 1 req/min
(HTTP 429), which made the first live-query attempt return artificial zeros.
Those invalid results were moved to logs/*_RATE_LIMITED_INVALID.csv.
The data below is REAL Wikidata RDF (70 entities, zh/en labels, 8 predicates),
downloaded verbatim and saved; all 39 queries are executed offline against
the resulting rdflib graph — no rate limits, fully reproducible.

Leakage control:
  NO_SUPERVISION      surface matching only; train/test alignment maps unused.
  MATCHED_SUPERVISION receives the TRAIN-POOL zh<->en label map (49 entities),
                      disjoint from 21 held-out TEST entities. Test gold
                      mappings are NEVER given.
  ORACLE              gold URI given directly — UPPER BOUND ONLY.
"""
from __future__ import annotations
import json
from pathlib import Path
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDFS

ROOT = Path(__file__).resolve().parent
WIKI = Namespace("http://www.wikidata.org/entity/")
PROP = Namespace("http://www.wikidata.org/prop/direct/")


def build_graph():
    ents = json.loads((ROOT / "entities.json").read_text())
    attrs = json.loads((ROOT / "attributes.json").read_text())
    g = Graph()
    for e in ents:
        u = URIRef(e["uri"])
        g.add((u, RDFS.label, Literal(e["zh"], lang="zh")))
        g.add((u, RDFS.label, Literal(e["en"], lang="en")))
    for qid, props in attrs.items():
        u = URIRef(str(WIKI) + qid)
        for p, vs in props.items():
            for v in vs:
                g.add((u, URIRef(str(PROP) + p), URIRef(str(WIKI) + v)))
    return g


def main():
    g = build_graph()
    ents = json.loads((ROOT / "entities.json").read_text())
    queries = json.loads((ROOT / "QUERIES.json").read_text())
    split = max(1, int(len(ents) * 0.7))
    train, test = ents[:split], ents[split:]
    # train-only alignment: zh label -> URI (train pool only)
    train_zh2uri = {e["zh"]: e["uri"] for e in train}
    # Language-partitioned surface index: cross-lingual queries (Chinese
    # mentions) can only access the ENGLISH label index — modelling two
    # heterogeneous platforms with no shared labels. This is the fair
    # "no alignment" condition; an alignment table is the only bridge.
    label2uri_zh, label2uri_en = {}, {}
    for s, _p, o in g.triples((None, RDFS.label, None)):
        lang = o.language if isinstance(o, Literal) else None
        if lang == "zh":
            label2uri_zh.setdefault(str(o), []).append(str(s))
        elif lang == "en":
            label2uri_en.setdefault(str(o), []).append(str(s))

    rows = []
    for q in queries:
        gold = q["gold_uri"]
        gold_vals = [str(v) for v in q["gold_values"]]
        fam = q["family"]
        # cross-lingual: Chinese mention, target view is English-labelled
        mention = (q["zh_label"] if fam == "cross-lingual"
                   else q["text"].split("的")[0])
        target_index = label2uri_en if fam == "cross-lingual" else label2uri_zh
        for group in ("NO_SUPERVISION", "MATCHED_SUPERVISION", "ORACLE"):
            ranked = []
            if group == "ORACLE":
                ranked = [gold]
            else:
                if group == "MATCHED_SUPERVISION" and fam == "cross-lingual":
                    # train-pool alignment: Chinese label -> URI (train only;
                    # held-out test mentions are absent from this map)
                    a = train_zh2uri.get(q["zh_label"])
                    if a:
                        ranked.append(a)
                # surface match restricted to target language index
                ranked += [u for u in target_index.get(mention, []) if u not in ranked]
            # evidence: objects of the top-ranked URI in local graph
            top = ranked[0] if ranked else None
            objs = [str(o) for _s, _p, o in g.triples((URIRef(top), None, None))] if top else []
            # value may be a label of the object entity (one-hop QIDs)
            label_objs = []
            for o in objs:
                label_objs += [str(l) for _s, _p, l in g.triples((URIRef(o), RDFS.label, None))]
            evidence = set(objs) | set(label_objs) | set([q.get("zh_label", "")])
            # gold values are QIDs -> compare both raw and expanded-to-URI form
            gold_norm = set()
            for v in gold_vals:
                gold_norm.add(v)
                if v.startswith("Q"):
                    gold_norm.add(str(WIKI) + v)
            vic = 1.0 if any(v in evidence for v in gold_norm) else 0.0
            rank = next((i for i, u in enumerate(ranked) if u == gold), -1)
            rows.append({"qid": q["qid"], "family": fam, "group": group,
                         "system": "local_sparql_surface",
                         "hits1": 1.0 if rank == 0 else 0.0,
                         "mrr": 0.0 if rank < 0 else 1.0/(rank+1),
                         "ac1": 1.0 if (rank == 0 and vic == 1.0) else 0.0,
                         "vic": vic, "n_candidates": len(ranked),
                         "gold_entity": q["gold_entity"],
                         "test_gold_used_as_input": group == "ORACLE"})

    import pandas as pd
    t = pd.DataFrame(rows)
    out = ROOT / "EXPERIMENT_RESULTS.csv"
    t.to_csv(out, index=False)
    print(f"graph: {len(g)} real triples; wrote {out} rows={len(t)}")
    print(t.groupby(["group", "family"])[["hits1", "ac1", "vic"]].mean().round(4).to_string())

if __name__ == "__main__":
    main()
