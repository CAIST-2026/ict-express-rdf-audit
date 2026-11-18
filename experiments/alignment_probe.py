"""Alignment-supervision probe: how much of the "LLM alignment" is given away?

This is the validity check the original submission never ran, and it is the one
that decides what the paper may claim.

Observation that motivated it
-----------------------------
`engine.OllamaLLMFilter` builds its prompt from
``candidate_entities`` = for each surface anchor, the *simulated LLM memory*
entry ``knowledge[canonical]`` = the ground-truth list of surface forms of that
entity in BOTH graphs, plus every URI those forms resolve to. When the simulated
memory covers an entity (``coverage=0.92``), the cross-lingual counterpart URI is
therefore inside the prompt, and the "alignment decision" reduces to selecting a
URI that was handed to the model.

The probe labels every query by whether the gold URI appears verbatim in the
prompt the aligner receives, then cross-tabulates that label against the
recorded per-query outcome. It needs no model calls: it re-derives the prompt
payload from the same deterministic generator + memory seeds as the main run,
and joins it to ``outputs_audit/experimental_results.csv`` by ``qid``.

Outputs (to --out):
  probe_by_group.csv   hits1 / ac1 / rank by gold-in-prompt status
  probe_per_query.csv  per-query label + outcome
  probe_config.json    seeds, coverage, counts

Interpretation
--------------
  * gold_given, hits1 > 0  -> the LLM selects among given candidates
  * gold_not_given, hits1  -> the LLM must supply knowledge the table lacks
A zero in the second cell means cross-lingual performance is bound by the
supplied table, not by model knowledge; the paper must say so.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Portable source lookup: RDF_LLM_EA_SRC env var overrides the bundled copy.
SRC = Path(os.environ.get(
    "RDF_LLM_EA_SRC",
    str(Path(__file__).resolve().parents[1] / "upstream")))
sys.path.insert(0, str(SRC))

from engine import CandidateAnchorMapper  # noqa: E402
from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import build_dataset, build_llm_memory  # noqa: E402

ALIAS_PREDS = {"A": ["http://example.org/schemaA/别名"],
               "B": ["http://example.org/schemaB/alias"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", type=int, default=50_000)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--coverage", type=float, default=0.92)
    ap.add_argument("--memory-seed", type=int, default=20260104,
                    help="seed used by the main run for build_llm_memory")
    ap.add_argument("--results", required=True,
                    help="per-query CSV from the main run")
    ap.add_argument("--variant", default="full_system")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bundle = build_dataset(args.triples, seed=args.seed)
    n_1 = args.queries * 2 // 5
    n_2 = args.queries * 3 // 10
    bench = build_benchmark(bundle, n_1hop=n_1, n_2hop=n_2,
                            n_cross=args.queries - n_1 - n_2, seed=args.seed + 1)
    knowledge, label_to_key, alias_index, _uri_graph = build_llm_memory(
        bundle, coverage=args.coverage, seed=args.memory_seed)
    mapper = CandidateAnchorMapper(bundle.graphs, ALIAS_PREDS)

    # ---- re-derive, per query, whether the gold URI is in the prompt -------
    # Applicability: the prompt supplies *entity* (person) profiles. The probe
    # is therefore only meaningful where the gold answer is that entity itself:
    #   1-hop          gt = person URIs      -> applicable
    #   cross-lingual  gt = single-URI counterpart of a person -> applicable
    #   2-hop          gt = WORK URIs reached by traversal; the person link is
    #                  the aligned part, but the gold URI never is -> n/a.
    APPLICABLE = {"1-hop", "cross-lingual"}
    given: dict[str, bool] = {}
    n_cand: dict[str, int] = {}
    for q in bench.queries:
        anchors, _sc = mapper.candidates(q.text)
        seen: set[str] = set()
        uris: set[str] = set()
        for a in anchors:
            canon = (label_to_key.get(CandidateAnchorMapper.normalize(a.label))
                     if a.label else None)
            if canon is None or canon in seen:
                continue
            seen.add(canon)
            for form in knowledge.get(canon, []):
                for u, _g in alias_index.get(form, ()):
                    uris.add(u)
        given[q.qid] = any(str(g) in uris for g in q.gt_uris)
        n_cand[q.qid] = len(uris)

    # ---- join with recorded outcomes --------------------------------------
    per_query = []
    with open(args.results, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["variant"] != args.variant:
                continue
            qid = r["qid"]
            per_query.append({
                "qid": qid, "category": r["category"],
                "gold_in_prompt": int(given.get(qid, False)),
                "n_prompt_uris": n_cand.get(qid, 0),
                "hits1": float(r["hits1"]), "mrr": float(r["mrr"]),
                "ac1": float(r.get("success_strict") or 0.0),
            })

    with open(out / "probe_per_query.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_query[0].keys()))
        w.writeheader()
        w.writerows(per_query)

    agg: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "h": 0.0, "a": 0.0, "m": 0.0})
    for r in per_query:
        if r["category"] not in APPLICABLE:
            grp = "not_applicable"
        else:
            grp = "gold_in_prompt" if r["gold_in_prompt"] else "gold_absent"
        key = (r["category"], grp)
        a = agg[key]
        a["n"] += 1
        a["h"] += r["hits1"]
        a["a"] += r["ac1"]
        a["m"] += r["mrr"]

    rows = []
    for (cat, grp), a in sorted(agg.items()):
        rows.append({"category": cat, "group": grp, "n": a["n"],
                     "hits1": round(a["h"] / a["n"], 4),
                     "mrr": round(a["m"] / a["n"], 4),
                     "ac1": round(a["a"] / a["n"], 4)})
    with open(out / "probe_by_group.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["category", "group", "n", "hits1", "mrr", "ac1"])
        w.writeheader()
        w.writerows(rows)

    cross = [r for r in per_query if r["category"] == "cross-lingual"]
    n_given = sum(r["gold_in_prompt"] for r in cross)
    cfg = {
        "triples": args.triples, "queries": args.queries, "seed": args.seed,
        "coverage": args.coverage, "memory_seed": args.memory_seed,
        "variant": args.variant,
        "applicable_categories": sorted(APPLICABLE),
        "cross_n": len(cross), "cross_gold_in_prompt": n_given,
        "cross_gold_in_prompt_frac": round(n_given / max(1, len(cross)), 4),
        "source_results": str(args.results),
    }
    (out / "probe_config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in rows:
        print(f"{r['category']:<14} {r['group']:<14} n={r['n']:<4} "
              f"hits1={r['hits1']:.3f} mrr={r['mrr']:.3f} ac1={r['ac1']:.3f}")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
