"""500-query benchmark generator for the scaled heterogeneous KG store.

Query families (500 total, stratified so each ablation is informative):

  1-hop          200   ask a scalar attribute of ONE entity, in the graph
                       that owns the fact (zh -> A, en -> B).
  2-hop          150   ask a genre / publication year of the entity's work,
                       which requires person -> work -> attribute traversal.
  cross-lingual  150   the query is posed in one graph's language but the only
                       copy of the answer lives in the OTHER graph
                       (zh query + B-only award, en query + A-only pen name),
                       so success is impossible without LLM alignment.

Ground truth is read from the generated entity records, never invented.
Ranking GT is the URI of the branch that actually holds the answer, which
makes Hits@1 / MRR sensitive to *which* branch the aligner surfaced first.

Design note: homonym (polysemous) entities are excluded from the subject pool
on purpose - a surface-only query naming them is genuinely ambiguous, so they
would measure annotation ambiguity rather than system quality. They remain in
the store as index-level distractors.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from scalable_data import Bundle, Entity, SEED

# intent -> (zh predicate variants, en predicate variants).
# An intent is only queried on a side whose fact dictionary carries one of its
# predicate names, so e.g. "award" (English-only) never yields a Chinese 1-hop
# query with no possible answer.
INTENTS = {
    "birth":       (["出生年份", "出生年"], ["birthYear", "yearOfBirth"]),
    "death":       (["逝世年份"], ["deathYear"]),
    "occupation":  (["职业", "职业类别"], ["occupation", "profession"]),
    "nationality": (["国籍"], ["nationality"]),
    "birthplace":  (["出生地", "出生地点"], ["birthPlace", "placeOfBirth"]),
    "award":       (["获奖"], ["award"]),
    "alias":       (["别名"], ["alias"]),
}
WORK_INTENTS = {
    "genre":   (["体裁"], ["genre"]),
    "publish": (["出版年份"], ["publicationYear"]),
}

TEMPLATES_ZH = {
    "birth": ["{n}的出生年份是什么？", "{n}是哪一年出生的？"],
    "death": ["{n}的逝世年份是什么？", "{n}是哪一年去世的？"],
    "occupation": ["{n}的职业是什么？", "{n}从事什么职业？"],
    "nationality": ["{n}的国籍是什么？"],
    "birthplace": ["{n}的出生地在哪里？", "{n}出生于哪里？"],
    "award": ["{n}获得过什么奖项？", "{n}拿过什么奖？"],
    "alias": ["{n}的别名是什么？"],
}
TEMPLATES_EN = {
    "birth": ["What is the birth year of {n}?", "When was {n} born?"],
    "death": ["What is the death year of {n}?"],
    "occupation": ["What is the occupation of {n}?"],
    "nationality": ["What is the nationality of {n}?"],
    "birthplace": ["Where was {n} born?"],
    "award": ["What award did {n} win?", "Which prize did {n} receive?"],
    "alias": ["What is the alias of {n}?"],
}
TEMPLATES_WORK_ZH = {
    "genre": ["{n}的代表作的体裁是什么？", "{n}的作品属于什么体裁？"],
    "publish": ["{n}的代表作是哪一年出版的？", "{n}的作品是什么时候出版的？"],
}
TEMPLATES_WORK_EN = {
    "genre": ["What is the genre of {n}'s notable work?",
              "Which genre does {n}'s notable work belong to?"],
    "publish": ["When was {n}'s notable work published?",
                "What is the publication year of {n}'s notable work?"],
}


@dataclass
class Query:
    qid: str
    text: str
    category: str
    lang: str
    intent: str
    constraints: list[str]
    gt_uris: list[str]
    gt_values: list[str]
    entity_key: str
    anchor_graph: str
    requires_alignment: bool = False


@dataclass
class Benchmark:
    queries: list = field(default_factory=list)

    def by_category(self) -> dict[str, list]:
        out: dict[str, list] = {}
        for q in self.queries:
            out.setdefault(q.category, []).append(q)
        return out


def _norm(values) -> list[str]:
    return [str(v) for v in values]


def _side_facts(e: Entity, side: str) -> dict:
    return e.facts_zh if side == "A" else e.facts_en


def build_benchmark(bundle: Bundle, n_1hop: int = 200, n_2hop: int = 150,
                    n_cross: int = 150, seed: int = SEED + 1) -> Benchmark:
    rng = random.Random(seed)
    # Subject pool: unambiguous entities only. Polysemous labels (duplicated
    # surface forms) are excluded from the benchmark - a surface-only query
    # naming them is genuinely ambiguous, so scoring it would measure
    # annotation ambiguity rather than system quality. They stay in the store
    # as index-level distractors that the matcher must rank around.
    zh_count: dict[str, int] = {}
    en_count: dict[str, int] = {}
    for e in bundle.entities:
        if e.zh_label:
            zh_count[e.zh_label] = zh_count.get(e.zh_label, 0) + 1
        if e.en_label:
            en_count[e.en_label] = en_count.get(e.en_label, 0) + 1
    pool = [e for e in bundle.entities
            if not e.key.startswith("H") and (e.a_uri or e.b_uri)
            and zh_count.get(e.zh_label, 0) == 1
            and en_count.get(e.en_label, 0) == 1]
    both = [e for e in pool if e.a_uri and e.b_uri]
    queries: list[Query] = []
    qid = 0

    def add(**kw):
        nonlocal qid
        queries.append(Query(qid=f"Q{qid:04d}", **kw))
        qid += 1

    # ---------------- 1-hop: half Chinese (A), half English (B) -------------
    side_pool = {"A": [e for e in pool if e.facts_zh],
                 "B": [e for e in pool if e.facts_en]}
    for k in range(n_1hop):
        lang = "zh" if k % 2 == 0 else "en"
        side = "A" if lang == "zh" else "B"
        cands = side_pool[side]
        e = cands[rng.randrange(len(cands))]
        facts = _side_facts(e, side)
        terms_of = 0 if side == "A" else 1          # index into INTENTS
        intents = [i for i in INTENTS
                   if any(t in facts for t in INTENTS[i][terms_of])]
        if not intents:
            continue
        intent = intents[rng.randrange(len(intents))]
        zh_terms = INTENTS[intent][0]
        en_terms = INTENTS[intent][1]
        present = [t for t in (zh_terms if side == "A" else en_terms) if t in facts]
        values = _norm(facts[present[0]])
        name = e.zh_label if side == "A" else e.en_label
        tmpl = (TEMPLATES_ZH if lang == "zh" else TEMPLATES_EN)[intent]
        add(text=tmpl[rng.randrange(len(tmpl))].format(n=name),
            category="1-hop", lang=lang, intent=intent,
            constraints=zh_terms + en_terms,
            # entity-level GT: either language node denotes the same KB entity
            gt_uris=e.all_uris(),
            gt_values=values, entity_key=e.key, anchor_graph=side)

    # ---------------- 2-hop: person -> work -> attribute --------------------
    works_pool = [e for e in pool if e.works and e.a_uri and e.b_uri]
    for k in range(n_2hop):
        lang = "zh" if k % 2 == 0 else "en"
        side = "A" if lang == "zh" else "B"
        e = works_pool[rng.randrange(len(works_pool))]
        intent = "genre" if k % 4 < 2 else "publish"
        zh_terms, en_terms = WORK_INTENTS[intent]
        works = e.works
        if intent == "genre":
            values = [w.genre_zh for w in works] + [w.genre_en for w in works]
        else:
            values = [str(w.year) for w in works]
        name = e.zh_label if side == "A" else e.en_label
        tmpl = (TEMPLATES_WORK_ZH if lang == "zh" else TEMPLATES_WORK_EN)[intent]
        # For 2-hop the *evidence node* is the work, so the ranking GT is the
        # work URI: a system must actually traverse person -> work to rank
        # first. Returning only the person node cannot answer the question.
        gt = [u for w in works for u in (w.a_uri, w.b_uri) if u]
        add(text=tmpl[rng.randrange(len(tmpl))].format(n=name),
            category="2-hop", lang=lang, intent=intent,
            constraints=zh_terms + en_terms, gt_uris=gt,
            gt_values=values, entity_key=e.key, anchor_graph=side)

    # ---------------- cross-lingual: answer lives in the OTHER graph --------
    # Direction 1: Chinese query, English-only award (must reach Graph B).
    award_pool = [e for e in both if "award" in e.facts_en]
    # Direction 2: English query, Chinese-only pen name (must reach Graph A).
    alias_pool = [e for e in both if "别名" in e.facts_zh]
    half = n_cross // 2
    for k in range(half):
        e = award_pool[rng.randrange(len(award_pool))]
        name = e.zh_label
        # sometimes name the entity by its Chinese pen name (alias mention)
        if "别名" in e.facts_zh and k % 4 == 3:
            name = e.facts_zh["别名"][0]
        tmpl = TEMPLATES_ZH["award"]
        add(text=tmpl[rng.randrange(len(tmpl))].format(n=name),
            category="cross-lingual", lang="zh", intent="award",
            constraints=INTENTS["award"][0] + INTENTS["award"][1],
            gt_uris=[e.b_uri], gt_values=_norm(e.facts_en["award"]),
            entity_key=e.key, anchor_graph="A", requires_alignment=True)
    for k in range(n_cross - half):
        e = alias_pool[rng.randrange(len(alias_pool))]
        name = e.en_label
        tmpl = TEMPLATES_EN["alias"]
        add(text=tmpl[rng.randrange(len(tmpl))].format(n=name),
            category="cross-lingual", lang="en", intent="alias",
            constraints=INTENTS["alias"][0] + INTENTS["alias"][1],
            gt_uris=[e.a_uri], gt_values=_norm(e.facts_zh["别名"]),
            entity_key=e.key, anchor_graph="B", requires_alignment=True)

    rng.shuffle(queries)
    for i, q in enumerate(queries):
        q.qid = f"Q{i:04d}"
    return Benchmark(queries=queries)
