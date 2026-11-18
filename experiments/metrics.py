"""Shared metric definitions for the ICT Express revision.

All systems are scored by exactly these functions so that the numbers in the
paper are comparable by construction. Definitions (see paper Section 4):

  hits1   : 1 iff a ground-truth node is ranked first.
  mrr     : 1/(rank+1) of the first ground-truth node, 0 if none retrieved.
  ac1     : "answer-in-context at rank 1" - the top-ranked node is a gold node
            AND a gold answer value occurs among the retrieved objects.
            This is the evidence-constrained (strict) accuracy. It is
            generator-free: it never looks at generated text.
  vic     : 1 iff a gold answer value occurs among the retrieved objects,
            regardless of ranking (evidence sufficiency, ranking-free).
  gsr     : triples inspected by the traversal / |store|.
  ctx     : number of context triples returned.

Rationale for ac1/vic: the legacy "end-to-end success" used substring matching
against a deterministic mock answerer and was shown by the audit to be
generator-coupled. ac1/vic depend only on retrieval, so they are reproducible
and cannot be inflated by the answer generator.
"""

from __future__ import annotations


def rank_of(gt_uris, ranked) -> int:
    gt = set(gt_uris)
    for i, uri in enumerate(ranked):
        if uri in gt:
            return i
    return -1


def score(res, gt_uris, gt_values, total_triples: int) -> dict:
    r = rank_of(gt_uris, res.ranked_uris)
    ctx_objs = {str(o) for _s, _p, o in res.triples}
    gold = [str(v) for v in gt_values]
    vic = 1.0 if any(v in ctx_objs for v in gold) else 0.0
    return {
        "hits1": 1.0 if r == 0 else 0.0,
        "mrr": 0.0 if r < 0 else 1.0 / (r + 1),
        "ac1": 1.0 if (r == 0 and vic == 1.0) else 0.0,
        "vic": vic,
        "rank": r,
        "ctx_triples": len(res.triples),
        "triples_scanned": res.scanned,
        "gsr": res.scanned / max(1, total_triples),
        "t_surface_ms": round(res.t_surface_ms, 4),
        "t_llm_ms": round(res.t_llm_ms, 4),
        "t_traversal_ms": round(res.t_traversal_ms, 4),
        "t_total_ms": round(res.e2e_ms, 4),
    }
