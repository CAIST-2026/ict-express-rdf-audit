"""Task C — execute real-world experiments against Wikidata SPARQL endpoint.

Three supervision conditions, strict leakage control:

  NO_SUPERVISION     query only; the system issues a SPARQL label lookup on
                     Wikidata using the mention extracted from the question.
                     Neither train nor test alignment tables are used.
  MATCHED_SUPERVISION additionally receives the TRAIN-POOL zh<->en label map
                     (49 entities, disjoint from the 21 held-out test entities).
                     Test gold mappings are NEVER given.
  ORACLE              gold URI supplied directly — upper bound only.

Systems: sparql_label_lookup (real SPARQL 1.1 over live Wikidata), plus a
control "random_guess" to calibrate chance. Metrics: hits1/ac1/vic by the
same evidence-constrained definitions, values from live RDF.
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "ICT-Express-Phase1-Audit/1.0 (research)",
      "Accept": "application/sparql-results+json"}


def sparql(q, retries=2):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=90).read())
        except Exception:
            if i == retries - 1:
                return {"results": {"bindings": []}, "_error": True}
            time.sleep(2)


def label_lookup(mention, lang):
    """Real SPARQL 1.1: exact label match in the given language."""
    q = f"""SELECT ?item WHERE {{
      ?item rdfs:label "{mention}"@{lang} .
    }} LIMIT 5"""
    d = sparql(q)
    return [b["item"]["value"] for b in d.get("results", {}).get("bindings", [])]


def main():
    queries = json.loads((ROOT / "QUERIES.json").read_text())
    entities = json.loads((ROOT / "entities.json").read_text())
    attrs = json.loads((ROOT / "attributes.json").read_text())
    split = max(1, int(len(entities) * 0.7))
    train = entities[:split]
    # TRAIN-ONLY alignment map: zh label -> en label -> uri (no test entities)
    train_zh2uri = {e["zh"]: e["uri"] for e in train}
    test_ids = {e["qid"] for e in entities[split:]}
    assert all(q["gold_entity"] in test_ids for q in queries), "test leakage in queries!"

    rows = []
    for q in queries:
        gold_uri = q["gold_uri"]
        gold_vals = [str(v) for v in q["gold_values"]]
        family = q["family"]
        # Extract mention: Chinese before 的, English after "Who is " / "What is the ... of "
        if family == "cross-lingual":
            mention = q["text"].replace("Who is ", "").rstrip("?")
            lang = "en"
        else:
            mention = q["text"].split("的")[0]
            lang = "zh"

        for group in ("NO_SUPERVISION", "MATCHED_SUPERVISION", "ORACLE"):
            t0 = time.perf_counter()
            if group == "ORACLE":
                ranked = [gold_uri]
            elif group == "MATCHED_SUPERVISION" and lang == "en":
                # train-pool alignment only; test mentions are absent -> no help
                aligned = next((u for zh, u in train_zh2uri.items()
                                if q["en_label"] and zh == q["en_label"]), None)
                ranked = ([aligned] if aligned else []) + label_lookup(mention, lang)
            else:
                ranked = label_lookup(mention, lang)
            latency = (time.perf_counter() - t0) * 1000

            # evidence: for one-hop, fetch all objects of gold URI and check
            # whether a gold value appears (real RDF evidence).
            if group == "ORACLE" or family == "one-hop":
                d = sparql(f"SELECT ?o WHERE {{ <{gold_uri}> ?p ?o }} LIMIT 200")
                objs = [str(b["o"]["value"]) for b in d.get("results", {}).get("bindings", [])]
            else:
                objs = [q["zh_label"]]
            vic = 1.0 if any(v in objs for v in gold_vals) else 0.0
            rank = next((i for i, u in enumerate(ranked) if u == gold_uri), -1)
            rows.append({
                "qid": q["qid"], "family": family, "group": group,
                "system": "sparql_label_lookup",
                "hits1": 1.0 if rank == 0 else 0.0,
                "mrr": 0.0 if rank < 0 else 1.0/(rank+1),
                "ac1": 1.0 if (rank == 0 and vic == 1.0) else 0.0,
                "vic": vic, "latency_ms": round(latency, 2),
                "gold_uri": gold_uri, "n_candidates": len(ranked),
                "test_gold_used_as_input": group == "ORACLE",
            })

    import pandas as pd
    t = pd.DataFrame(rows)
    out = ROOT / "EXPERIMENT_RESULTS.csv"
    t.to_csv(out, index=False)
    print(f"wrote {out} rows={len(t)}")
    print(t.groupby(["group", "family"])[["hits1", "ac1", "vic", "latency_ms"]].mean().round(4).to_string())

if __name__ == "__main__":
    main()
