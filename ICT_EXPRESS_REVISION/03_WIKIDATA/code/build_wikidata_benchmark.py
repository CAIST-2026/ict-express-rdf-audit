"""Revision Stage 4: expand and audit the authentic Wikidata RDF benchmark.

This script does not invent Wikidata records. It reads the saved authentic
SPARQL responses and derived files from ICT_EXPRESS_PHASE1, expands the query
set deterministically from those saved triples, executes a local
evidence-constrained surface/alignment experiment, and writes traceable CSVs.

Outputs are written under ICT_EXPRESS_REVISION/03_WIKIDATA/.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pandas as pd
from scipy.stats import beta

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
PHASE1 = ROOT / "ICT_EXPRESS_PHASE1" / "real_world_benchmark"
REV = ROOT / "ICT_EXPRESS_REVISION" / "03_WIKIDATA"

PRED_ZH = {
    "P27": "国籍",
    "P106": "职业",
    "P19": "出生地",
    "P20": "死亡地",
    "P1412": "语言",
    "P69": "母校",
    "P108": "雇主",
    "P463": "成员",
}
WIKI = "http://www.wikidata.org/entity/"


def cp_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided Clopper--Pearson exact binomial interval."""
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def copy_inputs() -> None:
    (REV / "raw_data").mkdir(parents=True, exist_ok=True)
    (REV / "processed_data").mkdir(parents=True, exist_ok=True)
    (REV / "queries").mkdir(parents=True, exist_ok=True)
    (REV / "results").mkdir(parents=True, exist_ok=True)
    (REV / "logs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PHASE1 / "RAW_SPARQL_RESPONSES.json",
                 REV / "raw_data" / "WIKIDATA_RAW_SPARQL_RESPONSES.json")
    shutil.copy2(PHASE1 / "entities.json",
                 REV / "processed_data" / "WIKIDATA_ENTITIES.json")
    shutil.copy2(PHASE1 / "attributes.json",
                 REV / "processed_data" / "WIKIDATA_ATTRIBUTES.json")


def build_queries(entities: list[dict], attrs: dict) -> pd.DataFrame:
    split = max(1, int(len(entities) * 0.7))
    rows: list[dict] = []
    for ent in entities:
        rows.append({
            "qid": f"RW2-X{len([r for r in rows]) + 1:04d}",
            "family": "cross-lingual",
            "text": f"请查找{ent['zh']}的英文资料",
            "subject_qid": ent["qid"],
            "gold_uri": ent["uri"],
            "gold_values": json.dumps([ent["en"]], ensure_ascii=False),
            "predicate": "label",
            "zh_label": ent["zh"],
            "en_label": ent["en"],
            "alignment_split": "train" if entities.index(ent) < split else "held-out",
            "source": "saved Wikidata zh/en rdfs:label",
        })
    n_one = 0
    for qid, props in attrs.items():
        ent = next(e for e in entities if e["qid"] == qid)
        for pred, values in props.items():
            if not values:
                continue
            n_one += 1
            rows.append({
                "qid": f"RW2-O{n_one:04d}",
                "family": "one-hop",
                "text": f"{ent['zh']}的{PRED_ZH.get(pred, pred)}是什么？",
                "subject_qid": qid,
                "gold_uri": WIKI + qid,
                "gold_values": json.dumps(values, ensure_ascii=False),
                "predicate": pred,
                "zh_label": ent["zh"],
                "en_label": ent["en"],
                "alignment_split": "train" if entities.index(ent) < split else "held-out",
                "source": "saved Wikidata direct property triple",
            })
    return pd.DataFrame(rows)


def execute(entities: list[dict], attrs: dict, queries: pd.DataFrame) -> pd.DataFrame:
    split = max(1, int(len(entities) * 0.7))
    train = entities[:split]
    train_zh2uri = {e["zh"]: e["uri"] for e in train}

    label_zh: dict[str, list[str]] = {}
    label_en: dict[str, list[str]] = {}
    for e in entities:
        label_zh.setdefault(e["zh"], []).append(e["uri"])
        label_en.setdefault(e["en"], []).append(e["uri"])

    objects: dict[str, list[str]] = {}
    for qid, props in attrs.items():
        uri = WIKI + qid
        vals: list[str] = []
        for vs in props.values():
            vals.extend(WIKI + v for v in vs)
        vals.extend([e["zh"] for e in entities if e["uri"] == uri])
        vals.extend([e["en"] for e in entities if e["uri"] == uri])
        objects[uri] = vals
    for e in entities:
        objects.setdefault(e["uri"], [e["zh"], e["en"]])

    out: list[dict] = []
    for q in queries.itertuples(index=False):
        gold_uri = q.gold_uri
        gold_values = [str(v) for v in json.loads(q.gold_values)]
        gold_norm = set(gold_values)
        gold_norm.update(WIKI + v for v in gold_values if v.startswith("Q"))
        target_index = label_en if q.family == "cross-lingual" else label_zh
        mention = q.zh_label
        for group in ("NO_SUPERVISION", "MATCHED_SUPERVISION", "ORACLE"):
            ranked: list[str] = []
            if group == "ORACLE":
                ranked = [gold_uri]
            else:
                if group == "MATCHED_SUPERVISION" and q.family == "cross-lingual":
                    a = train_zh2uri.get(q.zh_label)
                    if a:
                        ranked.append(a)
                ranked.extend(u for u in target_index.get(mention, []) if u not in ranked)
            top = ranked[0] if ranked else None
            evidence = set(objects.get(top, []))
            vic = float(any(v in evidence for v in gold_norm))
            rank = next((i for i, u in enumerate(ranked) if u == gold_uri), -1)
            out.append({
                "qid": q.qid,
                "family": q.family,
                "alignment_split": q.alignment_split,
                "group": group,
                "system": "local_surface_alignment",
                "hits1": float(rank == 0),
                "mrr": 0.0 if rank < 0 else 1.0 / (rank + 1),
                "ac1": float(rank == 0 and vic == 1.0),
                "vic": vic,
                "gold_entity": q.subject_qid,
                "gold_uri": gold_uri,
                "test_gold_used_as_input": group == "ORACLE",
            })
    return pd.DataFrame(out)


def summarize(perq: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    keys = [("ALL", None), ("family", "family"), ("split", "alignment_split")]
    for label, col in keys:
        groups = [("ALL", perq)] if col is None else list(perq.groupby(col))
        for name, g in groups:
            for fam in ["ALL", "one-hop", "cross-lingual"]:
                gg = g if fam == "ALL" else g[g.family == fam]
                if gg.empty:
                    continue
                for group in ["NO_SUPERVISION", "MATCHED_SUPERVISION", "ORACLE"]:
                    h = gg[gg.group == group]
                    if h.empty:
                        continue
                    k = int(h.ac1.sum())
                    n = int(len(h))
                    lo, hi = cp_ci(k, n)
                    rows.append({
                        "slice_by": label,
                        "slice": name,
                        "family": fam,
                        "group": group,
                        "n": n,
                        "hits1": round(float(h.hits1.mean()), 6),
                        "ac1": round(float(h.ac1.mean()), 6),
                        "vic": round(float(h.vic.mean()), 6),
                        "ac1_successes": k,
                        "ac1_ci95_low": round(lo, 6),
                        "ac1_ci95_high": round(hi, 6),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    copy_inputs()
    entities = json.loads((REV / "processed_data" / "WIKIDATA_ENTITIES.json").read_text())
    attrs = json.loads((REV / "processed_data" / "WIKIDATA_ATTRIBUTES.json").read_text())
    queries = build_queries(entities, attrs)
    queries.to_csv(REV / "queries" / "WIKIDATA_QUERY_SET.csv", index=False)

    gold = queries[["qid", "family", "subject_qid", "gold_uri", "gold_values",
                    "predicate", "alignment_split", "source"]].rename(
                        columns={"subject_qid": "gold_entity"})
    gold.to_csv(REV / "queries" / "WIKIDATA_GOLD_ANSWERS.csv", index=False)

    perq = execute(entities, attrs, queries)
    perq.to_csv(REV / "results" / "WIKIDATA_PER_QUERY_RESULTS.csv", index=False)
    summary = summarize(perq)
    summary.to_csv(REV / "results" / "WIKIDATA_EXPERIMENT_RESULTS.csv", index=False)

    print(f"queries={len(queries)} per_query_rows={len(perq)} summary_rows={len(summary)}")
    print(summary[(summary.slice_by == "ALL") &
                  (summary.family == "cross-lingual")].to_string(index=False))


if __name__ == "__main__":
    main()
