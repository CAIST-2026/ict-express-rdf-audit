"""Final-answer generation (RAG layer) + LLM-as-a-judge scoring.

Implements the two RAG quality metrics required by the experiment matrix:
  - Faithfulness: are the claims in the generated answer supported by the
    retrieved (pruned) context? Proves that pruning removes noise.
  - Answer Relevance: does the answer match the ground-truth values?
    Proves that pruning reduces hallucination-induced wrong answers.

Backends:
  - OpenAI (LLM-as-a-judge, the role ragas plays) when OPENAI_API_KEY is set
  - deterministic mock proxy otherwise (clearly flagged in all outputs)

The mock answerer simulates an LLM generator: it extracts values of the intent
predicates from the retrieved context; when the context has NO matching value
(mis-aligned retrieval), it "guesses" a plausible value from an unrelated
entity - the classic hallucination pattern that pruning should prevent.
"""

import json
import logging
import os

from engine import local_name

log = logging.getLogger("judge")


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------
class MockAnswerer:
    """Simulated generator.

    Behaviour modelled:
      * answers in the language of the question (a real assistant does),
        so bilingual context does not produce bilingual answers;
      * emits the two highest-ranked candidate values it can ground in the
        context, then stops - a top-k RAG with many candidate entities thus
        answers with a *set* of values, which is precisely how precision loss
        shows up in Answer Relevance;
      * when the context contains no value for the asked predicate it falls
        back to a parametric-memory guess (the hallucination pattern).
    """

    backend_name = "mock"

    def __init__(self, graphs: dict, exclude_uris=()):
        self.decoy: dict[str, list[str]] = {}
        excluded = set(exclude_uris)
        for g in graphs.values():
            for s, p, o in g:
                if str(s) in excluded:
                    continue
                self.decoy.setdefault(local_name(str(p)), []).append(str(o))

    @staticmethod
    def _has_cjk(text: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in text)

    def answer(self, query: str, triples, constraints) -> str:
        cs = set(constraints)
        want_cjk = self._has_cjk(query)
        same: list[str] = []
        other: list[str] = []
        for _s, p, o in triples:
            if local_name(str(p)) not in cs:
                continue
            v = str(o)
            if v.startswith("http"):
                continue
            bucket = same if self._has_cjk(v) == want_cjk else other
            if v not in bucket:
                bucket.append(v)
        vals = (same or other)[:2]
        if vals:
            return "; ".join(vals)
        for pl in cs:
            if pl in self.decoy:
                return self.decoy[pl][0]
        return "no answer"


class OpenAIAnswerer:
    backend_name = "openai"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._fb = MockAnswerer({})

    def answer(self, query: str, triples, constraints) -> str:
        ctx = "\n".join(f"{p} -> {o}" for _s, p, o in triples[:40]) or "(empty)"
        prompt = (f"User query: {query}\nRetrieved triples:\n{ctx}\n\n"
                  "Answer the query using ONLY the triples above. Be concise.")
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0)
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            log.warning("OpenAI answerer failed (%s); mock fallback", exc)
            return self._fb.answer(query, triples, constraints)


def get_answerer(graphs: dict, exclude_uris=()):
    if os.environ.get("OPENAI_API_KEY"):
        log.info("Answerer backend: OpenAI")
        return OpenAIAnswerer()
    log.info("Answerer backend: deterministic mock")
    return MockAnswerer(graphs, exclude_uris)


# ---------------------------------------------------------------------------
# LLM-as-a-judge
# ---------------------------------------------------------------------------
class MockJudge:
    """Deterministic judge proxy: faithfulness = claims grounded in the
    retrieved context; relevance = claims matching ground-truth values."""

    backend_name = "mock-proxy"

    def score(self, query: str, answer: str, context_triples, gt_values):
        claims = [c.strip() for c in (answer or "").split(";") if c.strip()]
        if not claims or answer == "no answer":
            return 0.0, 0.0
        ctx = {str(o) for _s, _p, o in context_triples}
        gt = {str(v) for v in gt_values}
        faith = sum(1 for c in claims if c in ctx) / len(claims)
        rel = sum(1 for c in claims if c in gt) / len(claims)
        return round(faith, 3), round(rel, 3)


class OpenAIJudge:
    backend_name = "openai-llm-as-judge"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._fb = MockJudge()

    def score(self, query: str, answer: str, context_triples, gt_values):
        ctx = "\n".join(f"{p} {o}" for _s, p, o in context_triples[:40])
        prompt = (
            "You are an evaluation judge for a RAG system. Score strictly.\n"
            f"User query: {query}\n"
            f"Retrieved context triples:\n{ctx}\n"
            f"Ground-truth answer values: {json.dumps(list(map(str, gt_values)))}\n"
            f"Generated answer: {answer}\n\n"
            'Return STRICT JSON: {"faithfulness": <0.0-1.0>, '
            '"answer_relevance": <0.0-1.0>} where faithfulness measures whether '
            "every claim in the answer is supported by the context triples, and "
            "answer_relevance measures whether the answer matches the ground truth."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0)
            data = json.loads(resp.choices[0].message.content)
            return (round(float(data["faithfulness"]), 3),
                    round(float(data["answer_relevance"]), 3))
        except Exception as exc:
            log.warning("OpenAI judge failed (%s); mock fallback", exc)
            return self._fb.score(query, answer, context_triples, gt_values)


class OllamaJudge:
    """Local LLM-as-a-judge (AUDIT FIX P2-2).

    The deterministic proxy cannot serve as independent evidence: the generator
    is only allowed to emit values taken from the retrieved context, so
    ``faithfulness`` degenerates to "did the generator have to fall back". This
    judge is an *independent* model that sees the context, the answer and the
    ground truth and scores grounding/relevance without knowing how the answer
    was produced.

    Kept separate from (and reported alongside) the proxy so that the change in
    the metric is measurable rather than silently substituted.
    """

    backend_name = "ollama-llm-as-judge"

    def __init__(self, model: str | None = None, host: str | None = None,
                 num_predict: int = 256):
        import requests
        self.requests = requests
        self.model = model or os.environ.get("OLLAMA_JUDGE_MODEL", "qwen2.5:7b")
        self.host = (host or os.environ.get("OLLAMA_HOST",
                                            "http://localhost:11434")).rstrip("/")
        self.num_predict = num_predict
        self._fb = MockJudge()
        self.n_calls = 0
        self.n_fallback = 0

    def score(self, query: str, answer: str, context_triples, gt_values):
        ctx = "\n".join(f"{p} -> {o}" for _s, p, o in context_triples[:40]) or "(empty)"
        gt = [str(v) for v in gt_values]
        prompt = (
            "You are a strict evaluator of a retrieval-augmented answering system.\n"
            f"Question: {query}\n"
            f"Retrieved context triples:\n{ctx}\n"
            f"Ground-truth answer values: {json.dumps(gt, ensure_ascii=False)}\n"
            f"System answer: {answer}\n\n"
            "Score:\n"
            "- faithfulness: fraction of the claims in the system answer that are "
            "supported by the retrieved context (0.0-1.0).\n"
            "- answer_relevance: fraction of the claims that match the ground-truth "
            "values (0.0-1.0).\n"
            'Return STRICT JSON only: {"faithfulness": <float>, '
            '"answer_relevance": <float>}'
        )
        self.n_calls += 1
        try:
            resp = self.requests.post(
                f"{self.host}/api/chat",
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "format": "json",
                      "options": {"temperature": 0,
                                  "num_predict": self.num_predict}},
                timeout=120)
            resp.raise_for_status()
            data = json.loads(resp.json()["message"]["content"])
            f = min(1.0, max(0.0, float(data["faithfulness"])))
            r = min(1.0, max(0.0, float(data["answer_relevance"])))
            return round(f, 3), round(r, 3)
        except Exception as exc:                      # pragma: no cover
            self.n_fallback += 1
            log.warning("Ollama judge failed (%s); mock fallback", exc)
            return self._fb.score(query, answer, context_triples, gt_values)


def get_judge(backend: str = "auto"):
    """backend: 'auto' | 'ollama' | 'openai' | 'mock'."""
    if backend == "ollama":
        log.info("Judge backend: local Ollama LLM-as-a-judge")
        return OllamaJudge()
    if backend == "mock":
        log.info("Judge backend: deterministic mock proxy (forced)")
        return MockJudge()
    if backend == "openai" or (backend == "auto" and os.environ.get("OPENAI_API_KEY")):
        log.info("Judge backend: OpenAI LLM-as-a-judge")
        return OpenAIJudge()
    log.info("Judge backend: deterministic mock proxy")
    return MockJudge()
