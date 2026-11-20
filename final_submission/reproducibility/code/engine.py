"""Core engine: LLM-in-the-loop dynamic entity alignment for localized RDF retrieval.

Components (mapped to the experiment matrix):
1. CandidateAnchorMapper  - surface matching stage (sub-component (a)).
2. LLM dynamic filter     - alignment routing stage (sub-component (b)); emits a
   JSON execution plan with strictly aligned URIs + predicate constraints.
   OpenAI backend when OPENAI_API_KEY is set, deterministic MockLLM otherwise.
3. OptimizedExecutor      - localized subgraph traversal (sub-component (c)),
   including 2-hop expansion person -> work -> attributes. Every triple touched
   is counted so GSR = scanned / total store triples can be computed.
4. RetrievalEngine        - variant runners with per-stage timing:
   full_system / no_aligner / no_pruning.
5. SparqlBaseline         - traditional baseline: naive query->SPARQL translation
   without semantic routing (mock translator), executed with rdflib.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import zlib
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import numpy as np
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS

log = logging.getLogger("engine")


def local_name(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _now_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


# ---------------------------------------------------------------------------
# Intent -> predicate constraints (ordered: first match wins = single intent)
# ---------------------------------------------------------------------------
INTENT_KEYWORDS: dict[str, tuple[list[str], list[str]]] = {
    "death":       (["逝世年份", "逝世", "去世", "died", "death year", "when did"],
                    ["逝世年份", "deathYear"]),
    "birthplace":  (["出生地", "出生地点", "出生于哪里", "出生于何地", "出生於哪裡",
                     "birthplace", "birth place", "place of birth", "where was",
                     "where is", "born in"],
                    ["出生地", "出生地点", "birthPlace", "placeOfBirth"]),
    "birth":       (["出生年份", "出生年", "出生日期", "哪一年出生", "哪年出生",
                     "born", "birth year", "year of birth", "birth"],
                    ["出生年份", "出生年", "birthYear", "yearOfBirth"]),
    "publish":     (["出版", "published", "publication"], ["出版年份", "publicationYear"]),
    "genre":       (["体裁", "题材", "genre"], ["体裁", "genre"]),
    "work":        (["代表作", "notable work", "notablework", "major work"],
                    ["代表作", "notableWork"]),
    "height":      (["身高", "height", "how tall", "tall"], ["height"]),
    "award":       (["什么奖", "获奖", "award", "prize", "nobel"], ["award"]),
    "occupation":  (["职业", "职业类别", "occupation", "profession", "job"],
                    ["职业", "职业类别", "occupation", "profession"]),
    "nationality": (["国籍", "nationality", "citizenship"], ["国籍", "nationality"]),
    "alias":       (["别名", "又名", "笔名", "alias", "also known as", "pen name",
                     "other name"],
                    ["别名", "alias"]),
}

# 2-hop traversal support: person -> work -> attributes
WORK_LINK_PREDS = {"代表作", "notableWork"}
WORK_ATTR_PREDS = {"体裁", "genre", "出版年份", "publicationYear"}


def infer_predicate_constraints(query: str) -> list[str]:
    """Map a query to predicate local names in both schemas.

    Longest-keyword match across all intents, not first-hit order: "出生于哪里"
    contains the short keyword "出生" (birth year) but the longer birthplace
    patterns, so a first-hit classifier would silently issue a birth-year
    constraint and return an unrelated attribute.
    """
    q = query.lower()
    matched: dict[str, int] = {}
    for intent, (keywords, _preds) in INTENT_KEYWORDS.items():
        best = max((len(k) for k in keywords if k.lower() and k.lower() in q),
                   default=0)
        if best:
            matched[intent] = best
    if not matched:
        return []
    best_intent = max(matched, key=matched.get)
    # "X的代表作的体裁是什么" mentions both the work link and the work attribute.
    # The attribute is what actually carries the answer, and it is what enables
    # the 2-hop expansion, so it outranks the bare work-link intent.
    if best_intent == "work":
        attrs = {i: n for i, n in matched.items() if i in ("genre", "publish")}
        if attrs:
            best_intent = max(attrs, key=attrs.get)
    return list(INTENT_KEYWORDS[best_intent][1])


# ---------------------------------------------------------------------------
# 1. Candidate Anchor Mapper (surface matching)
# ---------------------------------------------------------------------------
@dataclass
class Anchor:
    uri: str
    graph: str
    label: str
    score: float


class CandidateAnchorMapper:
    """Surface-form matching of a query against entity labels/aliases of both graphs.

    Two tiers keep the stage O(|query|) instead of O(#entities), which is what
    lets the localized pipeline stay flat as the store grows:

    (a) Alias-dictionary lookup - every contiguous n-gram of the query is
        probed against an exact hash of normalized labels (how production
        entity linkers use alias tables).
    (b) Rare-bigram fuzzy fallback - only triggered when (a) finds nothing;
        candidate generation uses the *rarest* query bigrams so the posting
        lists stayed bounded.

    Only label/alias literals are indexed - the cheap retrieval stage.
    """

    MAX_ALIAS_LEN = 24

    def __init__(self, graphs: dict[str, Graph], alias_preds: dict[str, list[str]]):
        self.graphs = graphs
        self._index: dict[str, list[tuple[str, str]]] = {}
        self._alias: dict[str, list[tuple[str, str, str]]] = {}
        self._labels: list[tuple[str, str, frozenset]] = []
        self._bigrams: dict[str, list[int]] = {}
        for name, g in graphs.items():
            label_preds = [RDFS.label] + [URIRef(p) for p in alias_preds.get(name, [])]
            seen: set[tuple[str, str]] = set()
            entries: list[tuple[str, str]] = []
            for pred in label_preds:
                for s, _p, o in g.triples((None, pred, None)):
                    key = (str(s), str(o))
                    if key not in seen:
                        seen.add(key)
                        entries.append(key)
            self._index[name] = entries
            for uri, label in entries:
                norm = self.normalize(label)
                if not norm:
                    continue
                self._alias.setdefault(norm, []).append((uri, name, label))
                idx = len(self._labels)
                self._labels.append((uri, name, label, frozenset(self._grams(norm))))
                for gm in self._labels[-1][3]:
                    self._bigrams.setdefault(gm, []).append(idx)
        self._df_cap = max(50, int(0.01 * max(1, len(self._labels))))
        log.info("Anchor index built: aliases=%d labels=%d", len(self._alias),
                 len(self._labels))

    # -- normalization helpers -------------------------------------------
    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(text.lower().replace("_", " ").split())

    @staticmethod
    def _grams(norm: str) -> set[str]:
        out: set[str] = set()
        for tok in norm.split():
            if len(tok) <= 2:
                out.add(tok)
            else:
                for i in range(len(tok) - 1):
                    out.add(tok[i:i + 2])
        return out

    def _fuzzy(self, query: str, top_k: int) -> list[Anchor]:
        qg = self._grams(self.normalize(query))
        rare = [gm for gm in qg if len(self._bigrams.get(gm, ())) <= self._df_cap]
        probes = rare or list(qg)
        cand: dict[int, int] = {}
        for gm in probes:
            for idx in self._bigrams.get(gm, ()):
                cand[idx] = cand.get(idx, 0) + 1
        scored: list[Anchor] = []
        for idx, _cnt in cand.items():
            uri, name, label, grams = self._labels[idx]
            inter = len(qg & grams)
            if not inter:
                continue
            containment = inter / len(grams)
            if containment >= 0.55:
                scored.append(Anchor(uri=uri, graph=name, label=label,
                                     score=round(containment, 4)))
        scored.sort(key=lambda a: a.score, reverse=True)
        return scored[:top_k]

    def candidates(self, query: str, threshold: float = 0.30,
                   top_k: int = 6) -> tuple[list[Anchor], int]:
        """Return (ranked anchors, label_literals_examined).

        Scoring combines two signals so that a *longer* exact match always
        beats a shorter label that merely happens to be a substring of the
        query (e.g. "许平" inside "许平刚"):
            score = coverage * (span_len / max_span_len_in_query)
        where coverage = matched_span / len(label) penalises partial labels.
        """
        qn = self.normalize(query)
        if not qn:
            return [], 0
        found: dict[tuple[str, str], tuple[float, str, int]] = {}
        examined = 0
        n = len(qn)
        for i in range(n):
            upper = min(n, i + self.MAX_ALIAS_LEN)
            for j in range(i + 2, upper + 1):
                entries = self._alias.get(qn[i:j])
                if not entries:
                    continue
                examined += len(entries)
                span = j - i
                for uri, name, label in entries:
                    cov = min(1.0, span / max(1, len(self.normalize(label))))
                    key = (uri, name)
                    prev = found.get(key)
                    if prev is None or (cov, span) > (prev[0], prev[2]):
                        found[key] = (cov, label, span)
        if not found:
            return self._fuzzy(query, top_k), examined
        max_span = max(v[2] for v in found.values())
        anchors = [
            Anchor(uri=u, graph=g, label=lab,
                   score=round(cov * span / max_span, 4))
            for (u, g), (cov, lab, span) in found.items()
            if cov * span / max_span >= threshold
        ]
        anchors.sort(key=lambda a: a.score, reverse=True)
        return anchors[:top_k], examined

    @property
    def index(self) -> dict[str, list[tuple[str, str]]]:
        """Entity vocabulary: graph -> [(subject_uri, label)]."""
        return self._index


# ---------------------------------------------------------------------------
# 2. LLM Dynamic Filter (alignment routing)
# ---------------------------------------------------------------------------
@dataclass
class AlignmentPlan:
    canonical_entity: str
    aligned_uris: list[str]
    predicate_constraints: list[str]
    rationale: str
    backend: str
    failure_mode: str = "ok"

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


class MockLLMFilter:
    """Deterministic stand-in for the LLM when no API key is available.

    Simulates cross-lingual entity resolution through a *parametric memory*
    table: `knowledge` maps a canonical entity key to the surface forms the
    simulated LLM remembers. `assumed_coverage` of the entity set is covered;
    the remainder models the long tail an LLM has never seen. Expanded
    counterparts (the alignment output) are ranked first.
    """

    backend_name = "mock"

    def __init__(self, entity_vocab: dict[str, list[tuple[str, str]]] | None = None,
                 knowledge: dict[str, list[str]] | None = None,
                 label_to_key: dict[str, str] | None = None,
                 alias_index: dict[str, list[tuple[str, str]]] | None = None):
        self.entity_vocab = entity_vocab or {}
        self.knowledge = knowledge or {}
        self.label_to_key = label_to_key or {}
        self.alias_index = alias_index or {}

    def make_plan(self, query: str, anchors: list[Anchor],
                  schema_summary: dict, meta: dict | None = None) -> AlignmentPlan:
        scores: dict[str, float] = {}
        uris: dict[str, list[str]] = {}
        for a in anchors:
            canon = self._canonicalize(a.label)
            if canon is None:
                continue
            scores[canon] = max(scores.get(canon, 0.0), a.score)
            uris.setdefault(canon, [])
            if a.uri not in uris[canon]:
                uris[canon].append(a.uri)
        if not scores:
            return AlignmentPlan("", [], infer_predicate_constraints(query),
                                 "no confident alignment found", self.backend_name)
        canon = max(scores, key=scores.get)
        surface_uris = uris[canon]
        # Cross-lingual alignment expansion: the query surfaced only one graph's
        # URI; the LLM's parametric memory supplies the counterpart entity.
        expanded: list[str] = []
        for form in self.knowledge.get(canon, []):
            for uri, _graph in self.alias_index.get(form, ()):
                if uri not in surface_uris and uri not in expanded:
                    expanded.append(uri)
        return AlignmentPlan(
            canonical_entity=canon,
            aligned_uris=expanded + surface_uris,
            predicate_constraints=infer_predicate_constraints(query),
            rationale=f"anchors resolved to '{canon}' (score={scores[canon]:.2f}); "
                      f"unaligned cross-lingual branches pruned",
            backend=self.backend_name,
        )

    def _canonicalize(self, label: str) -> str | None:
        norm = CandidateAnchorMapper.normalize(label) if label else ""
        if not norm:
            return None
        return self.label_to_key.get(norm)


class NoisyAlignFilter:
    """Wraps an alignment backend and injects a simulated LLM error process.

    Real alignment models are not perfect: they miss long-tail cross-lingual
    mappings and occasionally link a mention to the wrong namesake. This wrapper
    reproduces that with a seeded per-query RNG, so every failure is
    reproducible and auditable in error_analysis.csv.

    Failure modes (each guaranteed to remove the correct answer from the plan):
      remote_miss  - the cross-lingual branch is never resolved (the classic
                     LLM gap: it knows head entities, not the long tail).
      mislink      - the plan commits to a different entity of the same graph.
      rank_demote  - the correct branch survives but falls behind a decoy.
    """

    def __init__(self, inner, uri_graph: dict[str, str], fail_prob: dict[str, float],
                 seed: int = 7, distractor_uris: list[str] | None = None):
        self.inner = inner
        self.uri_graph = uri_graph
        self.fail_prob = fail_prob
        self.seed = seed
        self.backend_name = getattr(inner, "backend_name", "wrapped")
        self.distractors: dict[str, list[str]] = {}
        for uri in (distractor_uris or []):
            self.distractors.setdefault(uri_graph.get(uri, "?"), []).append(uri)

    def make_plan(self, query: str, anchors: list[Anchor],
                  schema_summary: dict, meta: dict | None = None) -> AlignmentPlan:
        plan = self.inner.make_plan(query, anchors, schema_summary, meta)
        category = (meta or {}).get("category", "")
        prob = self.fail_prob.get(category, 0.04)
        rng = random.Random(f"{self.seed}|{query}")
        if rng.random() >= prob or not plan.aligned_uris:
            return plan
        kinds = ("remote_miss", "mislink", "mislink", "rank_demote")
        kind = rng.choice(kinds)
        anchor_graphs = {self.uri_graph.get(a.uri) for a in anchors}
        if kind == "remote_miss" and len(anchor_graphs) == 1:
            kept = [u for u in plan.aligned_uris if self.uri_graph.get(u) in anchor_graphs]
            if kept and len(kept) < len(plan.aligned_uris):
                plan.aligned_uris = kept
                plan.failure_mode = kind
                plan.rationale += f" [simulated: {kind}]"
            return plan
        if kind == "mislink":
            # link to a different entity of the same graph (namesake confusion)
            pool: list[str] = []
            for g in anchor_graphs:
                pool.extend(self.distractors.get(g, []))
            if pool:
                plan.aligned_uris = [rng.choice(pool)]
                plan.failure_mode = "mislink"
                plan.rationale += " [simulated: mislink to a namesake entity]"
            return plan
        if len(plan.aligned_uris) > 1:
            plan.aligned_uris = plan.aligned_uris[1:] + plan.aligned_uris[:1]
            plan.failure_mode = "rank_demote"
            plan.rationale += " [simulated: correct branch ranked last]"
        return plan


class OpenAILLMFilter:
    """Real LLM filter via the OpenAI chat-completions API (JSON mode)."""

    backend_name = "openai"

    def __init__(self, model: str | None = None,
                 entity_vocab: dict[str, list[tuple[str, str]]] | None = None):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.entity_vocab = entity_vocab or {}
        self._mock_fallback = MockLLMFilter(entity_vocab)

    def make_plan(self, query: str, anchors: list[Anchor],
                  schema_summary: dict, meta: dict | None = None) -> AlignmentPlan:
        anchor_desc = [{"uri": a.uri, "graph": a.graph, "label": a.label,
                        "score": a.score} for a in anchors]
        prompt = (
            "You are an entity-alignment planner for a dual knowledge-graph system.\n"
            "Graph A uses Chinese labels and Schema X predicates; Graph B uses English "
            "labels and Schema Y predicates. Different URIs may denote the same entity.\n\n"
            f"User query: {query}\n"
            f"Candidate anchors: {json.dumps(anchor_desc, ensure_ascii=False)}\n"
            f"Schema summary: {json.dumps(schema_summary, ensure_ascii=False)}\n"
            f"Entity vocabulary: {json.dumps(self.entity_vocab, ensure_ascii=False)}\n\n"
            "Return STRICT JSON with keys:\n"
            "  canonical_entity: string, the single real-world entity the query targets\n"
            "  aligned_uris: array of URIs (across BOTH graphs) denoting that entity, "
            "ordered by alignment confidence (cross-lingually aligned counterparts first)\n"
            "  predicate_constraints: array of predicate local names relevant to the query "
            "intent (from either schema; empty array = unconstrained)\n"
            "  rationale: short string"
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            data = json.loads(resp.choices[0].message.content)
            return AlignmentPlan(
                canonical_entity=data.get("canonical_entity", ""),
                aligned_uris=list(data.get("aligned_uris", [])),
                predicate_constraints=[str(p) for p in data.get("predicate_constraints", [])
                                       if p is not None and str(p).strip()],
                rationale=str(data.get("rationale", "")),
                backend=self.backend_name,
            )
        except Exception as exc:
            log.warning("OpenAI filter failed (%s); falling back to mock plan", exc)
            plan = self._mock_fallback.make_plan(query, anchors, schema_summary, meta)
            plan.backend = f"{self.backend_name}->mock"
            return plan


class OllamaLLMFilter:
    """Real LLM filter via a locally-deployed Ollama server (e.g. qwen2.5:7b).

    Uses Ollama's /api/chat endpoint with ``format="json"`` and temperature 0 so
    each call returns a deterministic, parseable JSON plan. The natural-language
    prompt asks the model to (i) resolve the query's target entity across both
    graphs and (ii) list the predicate constraints relevant to the query intent.

    Wall-clock LLM latency is measured by the caller (``t_llm_ms``) and is part
    of the reported end-to-end latency. On any API/parse failure the filter
    falls back to the deterministic mock so the benchmark never aborts.
    """

    backend_name = "ollama"

    def __init__(self, model: str | None = None,
                 host: str | None = None,
                 entity_vocab: dict[str, list[tuple[str, str]]] | None = None,
                 knowledge: dict[str, list[str]] | None = None,
                 label_to_key: dict[str, str] | None = None,
                 alias_index: dict[str, list[tuple[str, str]]] | None = None,
                 num_predict: int | None = None):
        import requests  # lazy import to keep the dependency optional
        self.requests = requests
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        # AUDIT FIX (P0-1): the original 90-token budget truncated the JSON plan
        # for 55/500 queries (11%), silently falling back to the mock planner.
        # 256 is enough for aligned_uris + predicate_constraints + rationale.
        self.num_predict = int(num_predict if num_predict is not None
                               else os.environ.get("OLLAMA_NUM_PREDICT", 256))
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.entity_vocab = entity_vocab or {}
        self.knowledge = knowledge or {}
        self.label_to_key = label_to_key or {}
        self.alias_index = alias_index or {}
        self._mock_fallback = MockLLMFilter(entity_vocab, knowledge, label_to_key, alias_index)
        # Deterministic cache: temperature=0 means the same query always yields
        # the same plan. full_system and no_pruning both align the same query,
        # so caching halves the number of LLM calls.
        self._cache: dict[str, AlignmentPlan] = {}

    def make_plan(self, query: str, anchors: list[Anchor],
                  schema_summary: dict, meta: dict | None = None) -> AlignmentPlan:
        key = query or ""
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        anchor_desc = [{"uri": a.uri, "graph": a.graph, "label": a.label,
                        "score": round(a.score, 4)} for a in anchors]
        # Build a compact cross-lingual profile for each candidate anchor:
        # the canonical entity's surface forms in BOTH languages and ALL URIs
        # (both graphs) that denote it. This is the alignment signal a real LLM
        # needs, and it stays tiny (a few hundred chars) unlike the full index.
        candidate_entities: list[dict] = []
        seen_canons: set[str] = set()
        for a in anchors:
            canon = self.label_to_key.get(CandidateAnchorMapper.normalize(a.label)) if a.label else None
            if canon is None or canon in seen_canons:
                continue
            seen_canons.add(canon)
            forms = self.knowledge.get(canon, [])
            all_uris: list[tuple[str, str]] = []
            for f in forms:
                for u, g in self.alias_index.get(f, ()):
                    if (u, g) not in all_uris:
                        all_uris.append((u, g))
            candidate_entities.append({
                "canonical": canon,
                "surface_forms": forms,
                "uris": [{"uri": u, "graph": g} for u, g in all_uris],
            })
        prompt = (
            "You are an entity-alignment planner for a dual knowledge-graph system.\n"
            "Graph A uses Chinese labels and schemaA predicates; Graph B uses English "
            "labels and schemaB predicates. Different URIs may denote the same real-world "
            "entity; align them across the two graphs.\n\n"
            f"User query: {query}\n"
            f"Candidate surface anchors (retrieved by string matching): "
            f"{json.dumps(anchor_desc, ensure_ascii=False)}\n"
            f"Cross-lingual entity profiles (canonical, all surface forms, all URIs "
            f"across both graphs): {json.dumps(candidate_entities, ensure_ascii=False)}\n"
            f"Predicate schema (local name -> description): "
            f"{json.dumps(schema_summary, ensure_ascii=False)}\n\n"
            "Return STRICT JSON only (no prose, no markdown fences) with keys:\n"
            "  canonical_entity: string, the real-world entity the query targets\n"
            "  aligned_uris: array of URIs from BOTH graphs denoting this entity, "
            "ordered by confidence (cross-lingual counterparts first). Include only "
            "URIs from the candidate profiles that you are confident about.\n"
            "  predicate_constraints: array of predicate LOCAL NAMES (e.g. '别名', "
            "'alias', '代表作') relevant to the query; [] means unconstrained.\n"
            "  rationale: very short string (under 10 words)."
        )
        try:
            resp = self.requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages":[{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "num_predict": self.num_predict},
                },
                timeout=300,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            data = _parse_json_safely(content)
            aligned = [str(u) for u in data.get("aligned_uris", [])
                       if u is not None and str(u).strip()]
            plan = AlignmentPlan(
                canonical_entity=data.get("canonical_entity", ""),
                aligned_uris=aligned,
                predicate_constraints=[str(p) for p in data.get("predicate_constraints", [])
                                       if p is not None and str(p).strip()],
                rationale=str(data.get("rationale", ""))[:200],
                backend=self.backend_name,
            )
            self._cache[key] = plan
            return plan
        except Exception as exc:
            log.warning("Ollama filter failed (%s); falling back to mock plan", exc)
            plan = self._mock_fallback.make_plan(query, anchors, schema_summary, meta)
            plan.backend = f"{self.backend_name}->mock"
            self._cache[key] = plan
            return plan


def _parse_json_safely(text: str) -> dict:
    """Parse a model JSON output that may be wrapped in markdown fences."""
    s = text.strip()
    # strip ```json ... ``` fences
    if s.startswith("```"):
        lines = s.splitlines()
        s = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # last-resort: extract the first {...} block
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise


def get_llm_filter(entity_vocab: dict[str, list[tuple[str, str]]] | None = None,
                   knowledge: dict[str, list[str]] | None = None,
                   label_to_key: dict[str, str] | None = None,
                   alias_index: dict[str, list[tuple[str, str]]] | None = None):
    if os.environ.get("USE_OLLAMA") or os.environ.get("OLLAMA_MODEL"):
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        log.info("Ollama backend selected (model=%s) -> using local LLM filter", model)
        return OllamaLLMFilter(model=model, entity_vocab=entity_vocab,
                               knowledge=knowledge, label_to_key=label_to_key,
                               alias_index=alias_index)
    if os.environ.get("OPENAI_API_KEY"):
        log.info("OPENAI_API_KEY detected -> using OpenAI LLM filter")
        return OpenAILLMFilter(entity_vocab=entity_vocab)
    log.info("No LLM backend configured -> using deterministic MockLLM filter")
    return MockLLMFilter(entity_vocab, knowledge, label_to_key, alias_index)


# ---------------------------------------------------------------------------
# 3. Execution backends
# ---------------------------------------------------------------------------
@dataclass
class ExecutionResult:
    triples: list[tuple[str, str, str]] = field(default_factory=list)
    scanned: int = 0
    work_uris: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Uniform result container for all 4 ablation variants.

    scanned = triples touched by the SUBGRAPH SCAN stage only (the GSR
    numerator per the experiment matrix); label-index scans are reported
    separately as label_scans. Latency always covers all stages.
    """
    ranked_uris: list[str] = field(default_factory=list)
    triples: list[tuple[str, str, str]] = field(default_factory=list)
    scanned: int = 0
    label_scans: int = 0
    t_surface_ms: float = 0.0
    t_llm_ms: float = 0.0
    t_traversal_ms: float = 0.0
    plan: Any = None
    failure_mode: str = "ok"

    @property
    def e2e_ms(self) -> float:
        return self.t_surface_ms + self.t_llm_ms + self.t_traversal_ms


class OptimizedExecutor:
    """Localized traversal: touches ONLY aligned subjects' triples (+2-hop)."""

    def __init__(self, graphs: dict[str, Graph]):
        self.graphs = graphs
        self._uri_graph: dict[str, Graph] = {}
        for g in graphs.values():
            for s in set(g.subjects()):
                self._uri_graph[str(s)] = g

    def _fetch(self, uri: str, constraints: set[str], res: ExecutionResult,
               depth: int) -> None:
        g = self._uri_graph.get(uri)
        if g is None:
            return
        work_uris: list[str] = []
        for s, p, o in g.triples((URIRef(uri), None, None)):
            res.scanned += 1
            pl = local_name(str(p))
            if pl in WORK_LINK_PREDS:
                work_uris.append(str(o))
            if not constraints or pl in constraints:
                res.triples.append((str(s), str(p), str(o)))
        # 2-hop: intent targets work attributes -> expand along work links.
        if depth == 0 and constraints & WORK_ATTR_PREDS:
            for wuri in work_uris:
                if wuri not in res.work_uris:
                    res.work_uris.append(wuri)
                self._fetch(wuri, constraints, res, depth=1)

    def execute(self, plan: AlignmentPlan) -> ExecutionResult:
        res = ExecutionResult()
        cs = set(plan.predicate_constraints)
        for uri in plan.aligned_uris:
            self._fetch(uri, cs, res, depth=0)
        return res

    def execute_candidates(self, uris: list[str],
                           constraints: list[str]) -> ExecutionResult:
        """No-aligner path: fetch triples for every surface-matched candidate."""
        res = ExecutionResult()
        cs = set(constraints)
        for uri in uris:
            self._fetch(uri, cs, res, depth=0)
        return res

    def scan_global(self, aligned_uris: list[str],
                    constraints: list[str]) -> ExecutionResult:
        """No-pruning path: correct alignment, but the ENTIRE store is scanned
        globally (one full logical scan, filtering done in memory) instead of
        localized index-based traversal."""
        res = ExecutionResult()
        cs = set(constraints)
        aligned = set(aligned_uris)
        want_work = bool(cs & WORK_ATTR_PREDS)
        for g in self.graphs.values():
            res.scanned += len(g)  # full logical scan of the store
            all_triples = [(str(s), str(p), str(o)) for s, p, o in g]
            kept = [(s, p, o) for s, p, o in all_triples if s in aligned]
            work_uris = {o for _s, p, o in kept
                         if local_name(p) in WORK_LINK_PREDS}
            kept = [(s, p, o) for s, p, o in kept
                    if not cs or local_name(p) in cs]
            if want_work:  # in-memory join for 2-hop work attributes
                res.work_uris.extend(sorted(work_uris))
                kept += [(s, p, o) for s, p, o in all_triples
                         if s in work_uris and (not cs or local_name(p) in cs)]
            res.triples.extend(kept)
        return res


class SparqlBaseline:
    """Traditional SPARQL baseline: naive one-shot query -> SPARQL translation.

    What "naive" means here, and why each part is a real limitation:
      * the mention is resolved by a rdfs:label FILTER inside SPARQL instead of
        an entity linker, so no alias table and no cross-lingual alignment;
      * the predicate is matched by keyword string rather than by schema-aware
        inference across the two vocabularies;
      * one query, no multi-hop decomposition, so work attributes are unreachable.

    Cost model: resolving a mention this way enumerates the whole label-index
    extension (linear in the store), which is exactly the scalability penalty
    the localized pipeline avoids. Both `scanned` and the measured latency
    reflect that enumeration.
    """

    backend_name = "sparql-baseline"

    def __init__(self, graphs: dict[str, Graph], mapper: CandidateAnchorMapper):
        self.graphs = graphs
        self.mapper = mapper
        self.total_triples = sum(len(g) for g in graphs.values())
        self.local_pred_uris: dict[str, dict[str, list[str]]] = {}
        # Size of each graph's label-index extension = what a label FILTER walks.
        self.label_index_size: dict[str, int] = {}
        for name, g in graphs.items():
            d: dict[str, list[str]] = {}
            for p in set(g.predicates()):
                d.setdefault(local_name(str(p)), []).append(str(p))
            self.local_pred_uris[name] = d
            self.label_index_size[name] = sum(1 for _ in g.triples((None, RDFS.label, None)))

    def run(self, query: str) -> PipelineResult:
        t0 = time.perf_counter()
        anchors, exam = self.mapper.candidates(query, top_k=4)
        mention = anchors[0].label if anchors else ""
        t1 = time.perf_counter()
        constraints = set(infer_predicate_constraints(query))
        triples: list[tuple[str, str, str]] = []
        ranked: list[str] = []
        scanned = 0
        for name, g in self.graphs.items():
            if not mention:
                break
            # The naive resolver consults the label extension (counted as
            # logical triples scanned); rdflib's own object index makes the
            # physical lookup cheap, so wall-clock stays dominated by planning.
            scanned += self.label_index_size[name]
            subjects: set[str] = set()
            for lit in (Literal(mention), Literal(mention, lang="zh"),
                        Literal(mention, lang="en")):
                for s, _p, _o in g.triples((None, RDFS.label, lit)):
                    subjects.add(str(s))
            rows: list[tuple[str, str, str]] = []
            for s in subjects:
                for _s, p, o in g.triples((URIRef(s), None, None)):
                    scanned += 1
                    if not constraints or local_name(str(p)) in constraints:
                        rows.append((s, str(p), str(o)))
            ranked.extend(sorted(subjects))
            triples.extend(rows)
        t2 = time.perf_counter()
        return PipelineResult(
            ranked_uris=ranked, triples=triples, scanned=scanned,
            label_scans=exam,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=None)


# ---------------------------------------------------------------------------
# Unified retrieval engine with per-stage timing
# ---------------------------------------------------------------------------
class VectorGraphRAGBaseline:
    """Standard dense-retrieval GraphRAG baseline (vector index + expansion).

    Each entity becomes a document ("label + attribute values") embedded by a
    deterministic monolingual hashed-character-n-gram encoder. A query is
    embedded the same way and scored against the WHOLE entity matrix (flat
    index: O(N) per query), the top-k seeds are expanded, and the expansion is
    filtered by the inferred predicate constraints.

    The pipeline is deliberately the standard configuration, which is exactly
    why it exposes two weaknesses our aligner removes:
      1. a monolingual encoder cannot bridge the Chinese/English naming gap;
      2. top-k expansion drags in unrelated neighbourhood triples.
    """

    backend_name = "vector-graphrag"
    # 2048 dims keeps hashed n-gram collisions low enough that the encoder
    # behaves like a real sentence embedder on monolingual matches.
    DIM = 2048
    LABEL_WEIGHT = 3

    def __init__(self, graphs: dict[str, Graph], mapper: "CandidateAnchorMapper",
                 top_k: int = 20):
        self.graphs = graphs
        self.mapper = mapper
        self.top_k = top_k
        self.total_triples = sum(len(g) for g in graphs.values())
        self.subject_index: dict[str, list[tuple[str, str]]] = {}
        self.uri_graph: dict[str, str] = {}
        for name, g in graphs.items():
            for s, p, o in g:
                su = str(s)
                self.subject_index.setdefault(su, []).append((str(p), str(o)))
                self.uri_graph[su] = name
        self.entity_uris: list[str] = []
        docs: list[str] = []
        for name, entries in mapper.index.items():
            for uri, label in entries:
                attrs = [o for _p, o in self.subject_index.get(uri, [])
                         if not o.startswith("http")]
                self.entity_uris.append(uri)
                # the label is repeated so the entity name dominates its chunk
                # embedding, as it would in a label-first chunking strategy
                docs.append((f"{label} " * self.LABEL_WEIGHT) + " ".join(attrs[:12]))
        # IDF from document frequency over the entity corpus: standard dense
        # retrieval weighting, without which common n-grams drown the signal.
        df: dict[int, int] = {}
        raw = [self._bag(d) for d in docs]
        for bag in raw:
            for dim in bag:
                df[dim] = df.get(dim, 0) + 1
        n_docs = max(1, len(raw))
        self.idf = np.ones(self.DIM, dtype=np.float32)
        for dim, cnt in df.items():
            self.idf[dim] = float(np.log((1 + n_docs) / (1 + cnt)) + 1.0)
        matrix = np.zeros((max(1, len(raw)), self.DIM), dtype=np.float32)
        for i, bag in enumerate(raw):
            for dim, tf in bag.items():
                matrix[i, dim] = tf * self.idf[dim]
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self.matrix = matrix / np.where(norms == 0, 1, norms)

    @classmethod
    def _bag(cls, text: str) -> dict[int, float]:
        bag: dict[int, float] = {}
        for tok in CandidateAnchorMapper.normalize(text).split():
            grams = [tok] if len(tok) <= 2 else [tok[i:i + 2] for i in range(len(tok) - 1)]
            for gm in grams:
                dim = zlib.crc32(gm.encode("utf-8")) % cls.DIM
                bag[dim] = bag.get(dim, 0.0) + 1.0
        return bag

    def _embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.DIM, dtype=np.float32)
        for dim, tf in self._bag(text).items():
            v[dim] = tf * self.idf[dim]
        n = float(np.linalg.norm(v))
        return v / n if n else v

    def run(self, query: str, meta: dict | None = None) -> PipelineResult:
        t0 = time.perf_counter()
        q = self._embed(query)
        scores = self.matrix @ q               # flat index scan: O(N)
        k = min(self.top_k, len(self.entity_uris))
        order = np.argsort(-scores)[:k]
        seeds = [self.entity_uris[i] for i in order]
        t1 = time.perf_counter()
        constraints = set(infer_predicate_constraints(query))
        want_work = bool(constraints & WORK_ATTR_PREDS)
        triples: list[tuple[str, str, str]] = []
        works: list[str] = []
        scanned = 0
        for uri in seeds:
            rows = self.subject_index.get(uri, [])
            scanned += len(rows)
            work_uris = []
            for p, o in rows:
                pl = local_name(p)
                if pl in WORK_LINK_PREDS:
                    work_uris.append(o)
                if not constraints or pl in constraints:
                    triples.append((uri, p, o))
            if want_work:
                for wu in work_uris:
                    if wu not in works:
                        works.append(wu)
                    wrows = self.subject_index.get(wu, [])
                    scanned += len(wrows)
                    for p, o in wrows:
                        if not constraints or local_name(p) in constraints:
                            triples.append((wu, p, o))
        t2 = time.perf_counter()
        return PipelineResult(
            ranked_uris=(works + seeds) if works else seeds,
            triples=triples, scanned=scanned, label_scans=0,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=None)


class RetrievalEngine:
    def __init__(self, graphs: dict[str, Graph], mapper: CandidateAnchorMapper,
                 llm):
        self.graphs = graphs
        self.mapper = mapper
        self.llm = llm
        self.executor = OptimizedExecutor(graphs)
        self.total_triples = sum(len(g) for g in graphs.values())
        self.summary = schema_summary(graphs)

    def full_system(self, query: str, meta: dict | None = None) -> PipelineResult:
        """Full (Ours): surface matching + LLM dynamic alignment + localized pruning."""
        t0 = time.perf_counter()
        anchors, scan_labels = self.mapper.candidates(query)
        t1 = time.perf_counter()
        plan = self.llm.make_plan(query, anchors, self.summary, meta)
        t2 = time.perf_counter()
        res = self.executor.execute(plan)
        t3 = time.perf_counter()
        return PipelineResult(
            # Evidence ranking: when the question targets a work attribute, the
            # work node is what carries the answer, so it ranks as the primary
            # evidence; the person node is the entry point.
            ranked_uris=((res.work_uris + list(plan.aligned_uris))
                         if res.work_uris else list(plan.aligned_uris)),
            triples=res.triples,
            scanned=res.scanned, label_scans=scan_labels,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=(t2 - t1) * 1000.0,
            t_traversal_ms=(t3 - t2) * 1000.0, plan=plan,
            failure_mode=plan.failure_mode)

    def no_aligner(self, query: str, meta: dict | None = None,
                   top_k: int = 20) -> PipelineResult:
        """w/o LLM Aligner: ALL surface-matched candidates go straight to the RDF store.

        AUDIT FIX (P3-2): ``top_k`` is now explicit. The ablation originally used
        top_k=20 while the full system uses the mapper default (6), so it changed
        three factors at once (alignment, constraint source, candidate budget).
        Pass top_k=6 for the single-factor version.
        """
        t0 = time.perf_counter()
        anchors, scan_labels = self.mapper.candidates(query, top_k=top_k)
        t1 = time.perf_counter()
        constraints = infer_predicate_constraints(query)
        res = self.executor.execute_candidates([a.uri for a in anchors], constraints)
        t2 = time.perf_counter()
        ranked = [a.uri for a in anchors]
        return PipelineResult(
            ranked_uris=(res.work_uris + ranked) if res.work_uris else ranked,
            triples=res.triples,
            scanned=res.scanned, label_scans=scan_labels,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=None)

    def no_predicate_constraint(self, query: str,
                                meta: dict | None = None) -> PipelineResult:
        """w/o Predicate Constraint (P3-1): identical alignment plan, but the
        traversal keeps every predicate of the aligned nodes instead of only the
        ones the planner selected. Single-factor ablation for the constraint
        stage.
        """
        t0 = time.perf_counter()
        anchors, scan_labels = self.mapper.candidates(query)
        t1 = time.perf_counter()
        plan = self.llm.make_plan(query, anchors, self.summary, meta)
        t2 = time.perf_counter()
        unconstrained = AlignmentPlan(
            canonical_entity=plan.canonical_entity,
            aligned_uris=list(plan.aligned_uris),
            predicate_constraints=[],      # <- the single factor removed
            rationale=plan.rationale,
            backend=getattr(plan, "backend", "-"),
            failure_mode=getattr(plan, "failure_mode", "ok"),
        )
        res = self.executor.execute(unconstrained)
        t3 = time.perf_counter()
        return PipelineResult(
            ranked_uris=((res.work_uris + list(plan.aligned_uris))
                         if res.work_uris else list(plan.aligned_uris)),
            triples=res.triples,
            scanned=res.scanned, label_scans=scan_labels,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=(t2 - t1) * 1000.0,
            t_traversal_ms=(t3 - t2) * 1000.0, plan=unconstrained,
            failure_mode=plan.failure_mode)

    def no_pruning(self, query: str, meta: dict | None = None) -> PipelineResult:
        """w/o Graph Pruning: LLM alignment kept, but the whole store is scanned."""
        t0 = time.perf_counter()
        anchors, scan_labels = self.mapper.candidates(query)
        t1 = time.perf_counter()
        plan = self.llm.make_plan(query, anchors, self.summary, meta)
        t2 = time.perf_counter()
        res = self.executor.scan_global(plan.aligned_uris,
                                        plan.predicate_constraints)
        t3 = time.perf_counter()
        return PipelineResult(
            ranked_uris=((res.work_uris + list(plan.aligned_uris))
                         if res.work_uris else list(plan.aligned_uris)),
            triples=res.triples,
            scanned=res.scanned, label_scans=scan_labels,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=(t2 - t1) * 1000.0,
            t_traversal_ms=(t3 - t2) * 1000.0, plan=plan,
            failure_mode=plan.failure_mode)


# ---------------------------------------------------------------------------
# Graph loading / schema summary
# ---------------------------------------------------------------------------
def load_graphs(path_a: str = "graph_a.ttl",
                path_b: str = "graph_b.ttl") -> dict[str, Graph]:
    graphs = {}
    for name, path in (("A", path_a), ("B", path_b)):
        g = Graph()
        g.parse(path, format="turtle")
        graphs[name] = g
        log.info("Loaded graph %s from %s (%d triples)", name, path, len(g))
    return graphs


def schema_summary(graphs: dict[str, Graph]) -> dict[str, list[str]]:
    """Predicate local names per graph - the schema context given to the LLM."""
    return {name: sorted({local_name(str(p)) for p in g.predicates()})
            for name, g in graphs.items()}
