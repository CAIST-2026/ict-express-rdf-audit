"""Multilingual dense-retrieval baseline without sentence-transformers.

The original submission's dense baseline used a *monolingual* hashed
character-bigram encoder: it cannot represent a Chinese and an English label in
a shared space, so its zero score on the cross-lingual family was a property of
the encoder rather than a finding about dense retrieval. This module provides
the fair version (intfloat/multilingual-e5-small, 384-d, mean-pooled, L2
normalised, e5's required "query: "/"passage: " prefixes) with the *same*
retrieval-then-traverse design, so the comparison isolates the encoder.

sentence-transformers is not used: it is unavailable in this environment (see
README, "Known limitations"); the encoder is reproduced with transformers +
torch, which is what sentence-transformers wraps for this model.

Interface matches engine.PipelineResult so metrics.py scores it identically.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from engine import (PipelineResult, WORK_ATTR_PREDS, WORK_LINK_PREDS,
                    infer_predicate_constraints, local_name)


def _mean_pool(last_hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    m = mask.unsqueeze(-1).to(last_hidden.dtype)
    return (last_hidden * m).sum(1) / m.sum(1).clamp(min=1e-6)


class DenseMultilingualBaseline:
    backend_name = "multilingual-e5-small"

    def __init__(self, graphs: dict, mapper, model_name: str = "intfloat/multilingual-e5-small",
                 top_k: int = 5, expand_work: bool = True, label_weight: int = 3,
                 batch_size: int = 64, device: str | None = None):
        from transformers import AutoModel, AutoTokenizer

        self.graphs = graphs
        self.mapper = mapper
        self.top_k = top_k
        self.expand_work = expand_work
        self.total_triples = sum(len(g) for g in graphs.values())
        self.model_name = model_name
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")

        self.subject_index: dict[str, list[tuple[str, str]]] = {}
        for g in graphs.values():
            for s, p, o in g:
                self.subject_index.setdefault(str(s), []).append((str(p), str(o)))

        self.entity_uris: list[str] = []
        docs: list[str] = []
        for _name, entries in mapper.index.items():
            for uri, label in entries:
                attrs = [o for _p, o in self.subject_index.get(uri, [])
                         if not o.startswith("http")]
                self.entity_uris.append(uri)
                docs.append("passage: " + (f"{label} " * label_weight)
                            + " ".join(attrs[:12]))
        self.n_docs = len(docs)

        t0 = time.perf_counter()
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()
        self.model_load_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        self.matrix = self._encode(docs, batch_size=batch_size)
        self.encode_s = time.perf_counter() - t0

    def _encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch = self.tok(texts[i:i + batch_size], padding=True,
                                 truncation=True, max_length=128,
                                 return_tensors="pt").to(self.device)
                h = self.model(**batch).last_hidden_state
                e = _mean_pool(h, batch["attention_mask"])
                e = torch.nn.functional.normalize(e, p=2, dim=1)
                out.append(e.cpu().numpy())
        return np.vstack(out).astype(np.float32)

    def run(self, query: str, meta: dict | None = None) -> PipelineResult:
        t0 = time.perf_counter()
        q = self._encode(["query: " + query])[0]
        scores = self.matrix @ q
        k = min(self.top_k, len(self.entity_uris))
        seeds = [self.entity_uris[i] for i in np.argsort(-scores)[:k]]
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
