"""Transliteration-based cross-lingual linker (no learned model, no LLM).

Why this baseline exists: on a bilingual graph whose Chinese and English labels
are romanisation pairs (王伟 / Wang Wei), cross-lingual entity linking reduces to
a phonetic string match. A 30-line matcher therefore tests whether the LLM's
cross-lingual contribution is a *capability* or a *cost*: if the matcher reaches
comparable cross-lingual accuracy at ~0.1 ms/query, the LLM is not necessary for
this data-generating process, and the paper must say so.

pypinyin is a general-purpose romanisation library; it is not the generator's
name table, so no ground-truth information leaks into the baseline.

Traversal, predicate constraints and cost accounting are identical to the full
system (engine.OptimizedExecutor), so only the linker differs.
"""

from __future__ import annotations

import time

from pypinyin import lazy_pinyin

from engine import (AlignmentPlan, PipelineResult, OptimizedExecutor,
                    infer_predicate_constraints, local_name)
from rdflib.namespace import RDFS


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("_", " ").split())


class TranslitLinker:
    backend_name = "translit"

    def __init__(self, graphs: dict, mapper, alias_preds: dict[str, list[str]] | None = None):
        self.graphs = graphs
        self._mapper = mapper
        self.total_triples = sum(len(g) for g in graphs.values())
        self.executor = OptimizedExecutor(graphs)
        self.alias_preds = alias_preds or {}
        self.zh_by_key: dict[str, list[str]] = {}
        self.en_by_key: dict[str, list[str]] = {}
        for name, g in graphs.items():
            preds = [RDFS.label] + [p for p in self.alias_preds.get(name, [])]
            for pred in preds:
                for s, _p, o in g.triples((None, pred, None)):
                    uri, lit = str(s), str(o)
                    if any("\u4e00" <= ch <= "\u9fff" for ch in lit):
                        key = _norm(" ".join(lazy_pinyin(lit)))
                        self.zh_by_key.setdefault(key, [])
                        if uri not in self.zh_by_key[key]:
                            self.zh_by_key[key].append(uri)
                    else:
                        key = _norm(lit)
                        self.en_by_key.setdefault(key, [])
                        if uri not in self.en_by_key[key]:
                            self.en_by_key[key].append(uri)

    def make_plan(self, query: str, anchors, schema_summary=None, meta=None) -> AlignmentPlan:
        constraints = infer_predicate_constraints(query)
        surface = [a.uri for a in anchors]
        expanded: list[str] = []
        for a in anchors:
            label = a.label or ""
            if any("\u4e00" <= ch <= "\u9fff" for ch in label):
                key = _norm(" ".join(lazy_pinyin(label)))
                pool = self.en_by_key.get(key, [])
            else:
                key = _norm(label)
                pool = self.zh_by_key.get(key, [])
            for uri in pool:
                if uri not in surface and uri not in expanded:
                    expanded.append(uri)
        return AlignmentPlan(
            canonical_entity=anchors[0].label if anchors else "",
            aligned_uris=expanded + surface,
            predicate_constraints=constraints,
            rationale="romanisation match",
            backend=self.backend_name)

    def run(self, query: str, meta: dict | None = None) -> PipelineResult:
        t0 = time.perf_counter()
        # same surface stage as every other system
        anchors, scan_labels = self._mapper.candidates(query)
        t1 = time.perf_counter()
        plan = self.make_plan(query, anchors)
        res = self.executor.execute(plan)
        t2 = time.perf_counter()
        return PipelineResult(
            ranked_uris=((res.work_uris + list(plan.aligned_uris))
                         if res.work_uris else list(plan.aligned_uris)),
            triples=res.triples, scanned=res.scanned, label_scans=scan_labels,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=plan)
