"""Additional, fairer baselines (Phase 2, P4).

Two gaps found by the audit are closed here:

1. The original "Vector GraphRAG" baseline used a *monolingual* hashed
   character-bigram encoder, so its cross-lingual score of 0.000 was a property
   of the encoder, not of dense retrieval. ``MLVectorBaseline`` replaces it with
   a genuinely multilingual encoder (intfloat/multilingual-e5-small), optionally
   combined with graph traversal.

2. The original "SPARQL baseline" never executed a SPARQL query: it walked
   rdflib triple patterns directly, with no multi-hop decomposition and no
   cross-lingual label handling, which made its 2-hop and cross-lingual zeros
   artefacts of the implementation. ``RealSparqlBaseline`` issues real SPARQL
   1.1 (rdflib ``Graph.query``), including a two-hop property path over work
   links and label matching in both languages and over alias predicates.

Both return the same ``PipelineResult`` container and count ``scanned`` with the
same convention (logical triples the system had to look at), so GSR stays
comparable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS

from engine import (PipelineResult, CandidateAnchorMapper,
                    WORK_ATTR_PREDS, WORK_LINK_PREDS,
                    infer_predicate_constraints, local_name)


@dataclass
class _Base:
    pass


# ---------------------------------------------------------------------------
# 1. Multilingual dense retrieval (+ optional graph traversal)
# ---------------------------------------------------------------------------
class MLVectorBaseline:
    """Multilingual dense retrieval over entity documents.

    Encoder: intfloat/multilingual-e5-small (384-d, explicitly multilingual).
    e5 requires the ``query: `` / ``passage: `` prefixes; using them is part of
    the model contract, not a tuning trick.

    ``expand_work=True`` additionally walks the work links of each seed (the
    graph-traversal component), so the pair (dense retrieval, dense retrieval +
    graph traversal) isolates what the graph step contributes.
    """

    backend_name = "multilingual-e5"

    def __init__(self, graphs: dict[str, Graph], mapper: CandidateAnchorMapper,
                 model_name: str = "intfloat/multilingual-e5-small",
                 top_k: int = 5, expand_work: bool = True,
                 label_weight: int = 3):
        from sentence_transformers import SentenceTransformer
        self.graphs = graphs
        self.mapper = mapper
        self.model_name = model_name
        self.top_k = top_k
        self.expand_work = expand_work
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
                docs.append(f"passage: " + (f"{label} " * label_weight)
                            + " ".join(attrs[:12]))

        t0 = time.perf_counter()
        self.model = SentenceTransformer(model_name)
        self.index_build_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        self.matrix = self.model.encode(docs, batch_size=64,
                                        normalize_embeddings=True,
                                        show_progress_bar=False)
        self.encode_build_s = time.perf_counter() - t0
        self.n_docs = len(docs)

    def run(self, query: str, meta: dict | None = None) -> PipelineResult:
        t0 = time.perf_counter()
        q = self.model.encode(["query: " + query], normalize_embeddings=True)[0]
        scores = self.matrix @ q
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
            if self.expand_work and want_work:
                for wu in work_uris:
                    if wu not in works:
                        works.append(wu)
                        wrows = self.subject_index.get(wu, [])
                        scanned += len(wrows)
                        for wp, wo in wrows:
                            if not constraints or local_name(wp) in constraints:
                                triples.append((wu, wp, wo))
        t2 = time.perf_counter()
        return PipelineResult(
            ranked_uris=(works + seeds) if works else list(seeds),
            triples=triples, scanned=scanned, label_scans=0,
            t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=None)


# ---------------------------------------------------------------------------
# 2. Real SPARQL baseline
# ---------------------------------------------------------------------------
class RealSparqlBaseline:
    """Real SPARQL 1.1 baseline executed by rdflib's query engine.

    Distinguishing features versus the original implementation:
      * an actual ``SELECT`` query is parsed and executed (``Graph.query``);
      * two-hop questions are answered with a property path over work links
        (``?s ?workLink ?w . ?w ?p ?o``), so 2-hop is reachable;
      * the mention is matched with ``CONTAINS`` over ``rdfs:label`` *and* the
        alias predicates, in both language-tagged and plain literals;
      * both graphs are queried and their results unioned.

    Execution is two-stage: stage A resolves the mention to entity URIs over
    ``rdfs:label`` *and* the alias predicates (both languages); stage B expands
    those URIs via ``VALUES``-injected bindings, with a two-hop pattern over the
    work links when the question asks for a work attribute.

    What it still cannot do, and why that is a genuine result rather than an
    artefact: the two graphs use different URIs for the same entity and there is
    no ``owl:sameAs`` link, so no query can cross the language boundary without
    an alignment step. That is precisely the capability under test.
    """

    backend_name = "sparql-real"

    def __init__(self, graphs: dict[str, Graph], mapper: CandidateAnchorMapper,
                 alias_preds: dict[str, list[str]] | None = None):
        self.graphs = graphs
        self.mapper = mapper
        self.alias_preds = alias_preds or {
            "A": ["http://example.org/schemaA/別名", "http://example.org/schemaA/别名"],
            "B": ["http://example.org/schemaB/alias"],
        }
        self.total_triples = sum(len(g) for g in graphs.values())
        self.label_index_size = {
            name: sum(1 for _ in g.triples((None, RDFS.label, None)))
            for name, g in graphs.items()}
        # local name -> URIs, per graph, for work links and predicates
        self.local_to_uri: dict[str, dict[str, list[str]]] = {}
        for name, g in graphs.items():
            d: dict[str, list[str]] = {}
            for p in set(g.predicates()):
                d.setdefault(local_name(str(p)), []).append(str(p))
            self.local_to_uri[name] = d
        self.n_sparql_calls = 0
        self.n_2hop_queries = 0
        self.n_resolve_hits = 0

    # ---- query text -----------------------------------------------------
    def _mention_filter(self, var: str = "?l") -> str:
        """Match the mention in label or alias, any language."""
        parts = [f"CONTAINS(STR({var}), ?mention)"]
        return " || ".join(parts)

    def _predicate_filter(self, constraints: set[str], var: str = "?p") -> str:
        if not constraints:
            return "true"
        # STRENDS on the local name; constraints come from a fixed vocabulary
        return " || ".join(f'STRENDS(STR({var}), "{c}")' for c in sorted(constraints))

    def _work_values(self, gname: str) -> str:
        uris = []
        for local in WORK_LINK_PREDS:
            uris.extend(self.local_to_uri.get(gname, {}).get(local, []))
        return " ".join(f"<{u}>" for u in uris)

    def _resolve_query(self, gname: str) -> str:
        """Stage A: resolve the mention to entity URIs (label OR alias)."""
        unions = ["{ ?s rdfs:label ?l . }"]
        for p in self.alias_preds.get(gname, []):
            unions.append(f"{{ ?s <{p}> ?l . }}")
        body = "\n                        UNION\n                        ".join(unions)
        return f"""
        SELECT DISTINCT ?s WHERE {{
          {body}
          FILTER({self._mention_filter('?l')})
        }} LIMIT 8
        """

    def run(self, query: str, meta: dict | None = None) -> PipelineResult:
        """Two-stage execution.

        Stage A resolves the surface mention to entity URIs with a real
        ``SELECT`` over labels/aliases; stage B expands those URIs with
        ``VALUES``-injected bindings.  Both stages are executed by rdflib's
        SPARQL 1.1 engine.  The original single-query formulation asked rdflib
        to materialise ``?s rdfs:label ?l . ?s ?p ?o`` before applying the
        mention filter, i.e. a full subject-extension join over ~8 k entities
        per question; pushing the selective binding down with ``VALUES`` is what
        any cost-based optimiser does, and it is required to make a pure-Python
        SPARQL engine tractable at 500 questions.
        """
        t0 = time.perf_counter()
        anchors, exam = self.mapper.candidates(query, top_k=4)
        mention = anchors[0].label if anchors else ""
        t1 = time.perf_counter()
        constraints = set(infer_predicate_constraints(query))
        want_work = bool(constraints & WORK_ATTR_PREDS)

        triples: list[tuple[str, str, str]] = []
        ranked: list[str] = []
        scanned = 0
        if mention:
            for name, g in self.graphs.items():
                scanned += self.label_index_size[name]
                work_vals = self._work_values(name)
                # ---- stage A: entity resolution ---------------------------
                self.n_sparql_calls += 1
                try:
                    subj_rows = list(g.query(
                        self._resolve_query(name),
                        initBindings={"mention": Literal(mention)}))
                except Exception:                      # pragma: no cover
                    subj_rows = []
                self.n_resolve_hits += len(subj_rows)
                if not subj_rows:
                    continue
                s_vals = " ".join(f"<{str(r[0])}>" for r in subj_rows)
                # ---- stage B: 2-hop over work links, or plain 1-hop -------
                if want_work and work_vals:
                    self.n_2hop_queries += 1
                    q = f"""
                    SELECT DISTINCT ?s ?w ?p ?o WHERE {{
                      VALUES ?s {{ {s_vals} }}
                      VALUES ?wp {{ {work_vals} }}
                      ?s ?wp ?w .
                      ?w ?p ?o .
                      FILTER({self._predicate_filter(constraints, '?p')})
                    }}"""
                else:
                    q = f"""
                    SELECT DISTINCT ?s ?p ?o WHERE {{
                      VALUES ?s {{ {s_vals} }}
                      ?s ?p ?o .
                      FILTER({self._predicate_filter(constraints, '?p')})
                    }}"""
                self.n_sparql_calls += 1
                try:
                    rows = g.query(q)
                except Exception:                      # pragma: no cover
                    rows = []
                for row in rows:
                    r = tuple(str(x) for x in row)
                    if len(r) == 4:                   # 2-hop shape
                        s, w, p, o = r
                        triples.append((w, p, o))
                        scanned += 1
                        if w not in ranked:
                            ranked.append(w)
                        if s not in ranked:
                            ranked.append(s)
                    else:
                        s, p, o = r
                        triples.append((s, p, o))
                        scanned += 1
                        if s not in ranked:
                            ranked.append(s)
        t2 = time.perf_counter()
        return PipelineResult(
            ranked_uris=ranked, triples=triples, scanned=scanned,
            label_scans=exam, t_surface_ms=(t1 - t0) * 1000.0, t_llm_ms=0.0,
            t_traversal_ms=(t2 - t1) * 1000.0, plan=None)
