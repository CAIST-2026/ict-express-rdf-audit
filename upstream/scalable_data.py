"""Parametric, scale-controlled heterogeneous RDF dataset generator.

Design goals (SCI Q2-grade experimental setup):
  * Arbitrary store size: 10K / 50K / 100K / 200K triples, built deterministically.
  * >= 2000 entities at the 50K operating point.
  * Real-world noise, three independent sources:
      1. Polysemy  - the same surface label denotes several distinct entities.
      2. Schema mismatch - synonym predicate names inside each schema
         (e.g. 出生年份 / 出生年, birthYear / yearOfBirth).
      3. Cross-lingual naming gap - Chinese and English labels share no
         characters, so surface matching alone cannot bridge graphs.

Graph A: Chinese labels + Schema X predicates.
Graph B: English labels + Schema Y predicates.
Overlapping entities are the same real-world person described twice.

The generated benchmark ground truth is recorded in `Entity` records, so the
experiment runner never invents answers.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

log = logging.getLogger("scalable_data")

# ---------------------------------------------------------------------------
# Namespaces (shared with the legacy generator so URIs stay comparable)
# ---------------------------------------------------------------------------
KGA = Namespace("http://example.org/kgA/entity/")
KGB = Namespace("http://example.org/kgB/entity/")
SX = Namespace("http://example.org/schemaA/")
SY = Namespace("http://example.org/schemaB/")
PERSON_A, PERSON_B = SX["Person"], SY["Person"]
WORK_A, WORK_B = SX["Work"], SY["Work"]

SEED = 20260101

# ---------------------------------------------------------------------------
# Predicate vocabularies.  The *canonical* name is what the benchmark uses;
# the alternates are injected into a fraction of long-tail entities only, so
# they act as pure schema noise (they raise the predicate vocabulary the LLM
# planner must reason over) without perturbing ground truth.
# ---------------------------------------------------------------------------
PRED = {
    "birth":     ("出生年份", "birthYear"),
    "death":     ("逝世年份", "deathYear"),
    "occupation": ("职业", "occupation"),
    "nationality": ("国籍", "nationality"),
    "birthplace": ("出生地", "birthPlace"),
    "alias":     ("别名", "alias"),
    "link":      ("代表作", "notableWork"),
    "genre":     ("体裁", "genre"),
    "year":      ("出版年份", "publicationYear"),
    "author":    ("作者", "author"),
}
ALT_PRED = {
    "出生年份": "出生年",
    "birthYear": "yearOfBirth",
    "出生地": "出生地点",
    "birthPlace": "placeOfBirth",
    "职业": "职业类别",
    "occupation": "profession",
}

# ---------------------------------------------------------------------------
# Character inventory with pinyin, so overlap pairs are phonetically plausible
# (林伟 <-> Lin Wei) instead of arbitrary.
# ---------------------------------------------------------------------------
SURNAME_PY = {
    "王": "Wang", "李": "Li", "张": "Zhang", "刘": "Liu", "陈": "Chen",
    "杨": "Yang", "黄": "Huang", "赵": "Zhao", "周": "Zhou", "吴": "Wu",
    "徐": "Xu", "孙": "Sun", "马": "Ma", "朱": "Zhu", "胡": "Hu",
    "郭": "Guo", "何": "He", "林": "Lin", "罗": "Luo", "郑": "Zheng",
    "梁": "Liang", "谢": "Xie", "宋": "Song", "唐": "Tang", "许": "Xu",
    "韩": "Han", "冯": "Feng", "邓": "Deng", "曹": "Cao", "彭": "Peng",
}
GIVEN_PY = {
    "伟": "Wei", "芳": "Fang", "娜": "Na", "敏": "Min", "静": "Jing",
    "磊": "Lei", "军": "Jun", "洋": "Yang", "勇": "Yong", "艳": "Yan",
    "杰": "Jie", "涛": "Tao", "明": "Ming", "超": "Chao", "秀": "Xiu",
    "霞": "Xia", "平": "Ping", "刚": "Gang", "华": "Hua", "玲": "Ling",
    "强": "Qiang", "健": "Jian", "颖": "Ying", "峰": "Feng", "宁": "Ning",
    "倩": "Qian", "宇": "Yu", "浩": "Hao", "晨": "Chen", "凯": "Kai",
}

EN_FIRST = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
            "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
            "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Nancy",
            "Daniel", "Lisa", "Matthew", "Margaret", "Anthony", "Sandra", "Mark",
            "Ashley", "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna"]
EN_LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
           "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
           "Wilson", "Anderson", "Taylor", "Moore", "Jackson", "Martin", "Lee",
           "Thompson", "White", "Harris", "Clark", "Lewis", "Walker", "Hall",
           "Allen", "Young", "King"]
EN_MIDDLE = [f"{c}." for c in "ABCDEFGHJKLMNPRSTW"]

ZH_OCCUP = [("作家", "writer"), ("诗人", "poet"), ("工程师", "engineer"),
            ("教师", "teacher"), ("医生", "doctor"), ("画家", "painter"),
            ("音乐家", "musician"), ("演员", "actor"), ("翻译家", "translator")]
ZH_CITY = [("北京", "Beijing"), ("上海", "Shanghai"), ("广州", "Guangzhou"),
           ("成都", "Chengdu"), ("西安", "Xi'an"), ("杭州", "Hangzhou"),
           ("南京", "Nanjing"), ("武汉", "Wuhan"), ("长沙", "Changsha"),
           ("青岛", "Qingdao")]
GENRE = [("小说", "novel"), ("诗歌", "poetry"), ("散文", "essay"),
         ("剧本", "drama"), ("学术专著", "monograph")]

AWARDS = ["National Book Award", "Lu Xun Literary Prize", "Mao Dun Literature Prize",
          "Golden Eagle Award", "National Science Prize", "International Poetry Prize",
          "Outstanding Artist Award", "Cultural Achievement Medal"]

# ---------------------------------------------------------------------------
# Curated core: real-world entities whose cross-lingual identity is common
# knowledge (this part is what a real LLM actually knows).
# ---------------------------------------------------------------------------
CORE_FACTS = [
    # zh, en, a_local, b_local, facts_zh, facts_en
    ("莫言", "Mo Yan", "莫言", "Mo_Yan",
     {"出生年份": [1955], "职业": ["作家"], "国籍": ["中国"], "出生地": ["山东高密"],
      "别名": ["管谟业"]},
     {"birthYear": [1955], "occupation": ["novelist"], "nationality": ["China"],
      "birthPlace": ["Gaomi, Shandong"], "award": ["Nobel Prize in Literature 2012"],
      "alias": ["Guan Moye"]}),
    ("鲁迅", "Lu Xun", "鲁迅", "Lu_Xun",
     {"出生年份": [1881], "逝世年份": [1936], "职业": ["作家"], "国籍": ["中国"],
      "出生地": ["浙江绍兴"], "别名": ["周树人"]},
     {"birthYear": [1881], "deathYear": [1936], "occupation": ["writer"],
      "nationality": ["China"], "birthPlace": ["Shaoxing, Zhejiang"],
      "alias": ["Zhou Shuren"]}),
    ("曹雪芹", "Cao Xueqin", "曹雪芹", "Cao_Xueqin",
     {"出生年份": [1715], "逝世年份": [1763], "职业": ["作家"], "国籍": ["中国"],
      "出生地": ["江苏南京"]},
     {"birthYear": [1715], "deathYear": [1763], "occupation": ["novelist"],
      "nationality": ["China"], "birthPlace": ["Nanjing, Jiangsu"]}),
    ("李白", "Li Bai", "李白", "Li_Bai",
     {"出生年份": [701], "逝世年份": [762], "职业": ["诗人"], "国籍": ["中国"],
      "出生地": ["四川江油"]},
     {"birthYear": [701], "deathYear": [762], "occupation": ["poet"],
      "nationality": ["China"], "birthPlace": ["Jiangyou, Sichuan"]}),
    ("杜甫", "Du Fu", "杜甫", "Du_Fu",
     {"出生年份": [712], "逝世年份": [770], "职业": ["诗人"], "国籍": ["中国"],
      "出生地": ["河南巩义"]},
     {"birthYear": [712], "deathYear": [770], "occupation": ["poet"],
      "nationality": ["China"], "birthPlace": ["Gongyi, Henan"]}),
    ("屠呦呦", "Tu Youyou", "屠呦呦", "Tu_Youyou",
     {"出生年份": [1930], "职业": ["科学家"], "国籍": ["中国"], "出生地": ["浙江宁波"]},
     {"birthYear": [1930], "occupation": ["pharmacologist"], "nationality": ["China"],
      "birthPlace": ["Ningbo, Zhejiang"],
      "award": ["Nobel Prize in Physiology or Medicine 2015"]}),
    ("姚明", "Yao Ming", "姚明", "Yao_Ming",
     {"出生年份": [1980], "职业": ["运动员"], "国籍": ["中国"], "出生地": ["上海"]},
     {"birthYear": [1980], "occupation": ["basketball player"],
      "nationality": ["China"], "birthPlace": ["Shanghai"], "height": [229]}),
    ("成龙", "Jackie Chan", "成龙", "Jackie_Chan",
     {"出生年份": [1954], "职业": ["演员"], "国籍": ["中国"], "出生地": ["香港"]},
     {"birthYear": [1954], "occupation": ["actor"], "nationality": ["China"],
      "birthPlace": ["Hong Kong"]}),
    ("张爱玲", "Eileen Chang", "张爱玲", "Eileen_Chang",
     {"出生年份": [1920], "逝世年份": [1995], "职业": ["作家"], "国籍": ["中国"],
      "出生地": ["上海"]},
     {"birthYear": [1920], "deathYear": [1995], "occupation": ["writer"],
      "nationality": ["China"], "birthPlace": ["Shanghai"]}),
    ("老子", "Laozi", "老子", "Laozi",
     {"出生年份": ["约公元前571年"], "职业": ["哲学家"], "国籍": ["中国"],
      "出生地": ["河南鹿邑"]},
     {"birthYear": [-571], "occupation": ["philosopher"], "nationality": ["China"],
      "birthPlace": ["Luyi, Henan"]}),
    ("屈原", "Qu Yuan", "屈原", "Qu_Yuan",
     {"出生年份": ["约公元前340年"], "职业": ["诗人"], "国籍": ["中国"],
      "出生地": ["湖北秭归"]},
     {"birthYear": [-340], "occupation": ["poet"], "nationality": ["China"],
      "birthPlace": ["Zigui, Hubei"]}),
    ("司马迁", "Sima Qian", "司马迁", "Sima_Qian",
     {"出生年份": ["约公元前145年"], "职业": ["史学家"], "国籍": ["中国"],
      "出生地": ["陕西韩城"]},
     {"birthYear": [-145], "occupation": ["historian"], "nationality": ["China"],
      "birthPlace": ["Hancheng, Shaanxi"]}),
    ("沈从文", "Shen Congwen", "沈从文", "Shen_Congwen",
     {"出生年份": [1902], "逝世年份": [1988], "职业": ["作家"], "国籍": ["中国"],
      "出生地": ["湖南凤凰"]},
     {"birthYear": [1902], "deathYear": [1988], "occupation": ["writer"],
      "nationality": ["China"], "birthPlace": ["Fenghuang, Hunan"]}),
    ("吴承恩", "Wu Cheng'en", "吴承恩", "Wu_Chengen",
     {"出生年份": [1500], "逝世年份": [1582], "职业": ["作家"], "国籍": ["中国"],
      "出生地": ["江苏淮安"]},
     {"birthYear": [1500], "deathYear": [1582], "occupation": ["novelist"],
      "nationality": ["China"], "birthPlace": ["Huai'an, Jiangsu"]}),
]

CORE_WORKS = [
    ("莫言", [("红高粱", "Red_Sorghum", "Red Sorghum", "小说", "novel", 1986),
             ("蛙", "Wa", "Frog", "小说", "novel", 2009)]),
    ("鲁迅", [("呐喊", "Na_Han", "Call to Arms", "小说集", "short story collection", 1923),
             ("彷徨", "Pang_Huang", "Wandering", "小说集", "short story collection", 1926)]),
    ("曹雪芹", [("红楼梦", "Hong_Lou_Meng", "Dream of the Red Chamber", "长篇小说", "novel", 1791)]),
    ("李白", [("静夜思", "Jing_Ye_Si", "Quiet Night Thoughts", "诗歌", "poetry", 726),
             ("将进酒", "Jiang_Jin_Jiu", "Invitation to Wine", "诗歌", "poetry", 752)]),
    ("杜甫", [("春望", "Chun_Wang", "Spring View", "诗歌", "poetry", 757),
             ("登高", "Deng_Gao", "Climbing High", "诗歌", "poetry", 767)]),
    ("屠呦呦", [("青蒿素", "Qing_Hao_Su", "Artemisinin", "研究论文", "research paper", 1977)]),
    ("成龙", [("警察故事", "Jing_Cha_Gu_Shi", "Police Story", "电影", "film", 1985)]),
    ("张爱玲", [("倾城之恋", "Qing_Cheng_Zhi_Lian", "Love in a Fallen City", "小说", "novel", 1943)]),
    ("老子", [("道德经", "Dao_De_Jing", "Tao Te Ching", "哲学著作", "philosophical text", -400)]),
    ("屈原", [("离骚", "Li_Sao", "Li Sao", "诗歌", "poetry", -278)]),
    ("司马迁", [("史记", "Shi_Ji", "Records of the Grand Historian", "史书", "historical text", -94)]),
    ("沈从文", [("边城", "Bian_Cheng", "Border Town", "小说", "novel", 1934)]),
    ("吴承恩", [("西游记", "Xi_You_Ji", "Journey to the West", "小说", "novel", 1592)]),
]

CORE_A_ONLY = [
    ("钱钟书", "钱钟书",
     {"出生年份": [1910], "职业": ["作家"], "国籍": ["中国"], "出生地": ["江苏无锡"]}),
    ("王羲之", "王羲之",
     {"出生年份": [303], "职业": ["书法家"], "国籍": ["中国"], "出生地": ["山东临沂"]}),
]
CORE_B_ONLY = [
    ("Su Shi", "Su_Shi",
     {"birthYear": [1037], "deathYear": [1101], "occupation": ["poet"],
      "nationality": ["China"], "birthPlace": ["Meishan, Sichuan"]}),
    ("Cao Yu", "Cao_Yu",
     {"birthYear": [1910], "occupation": ["playwright"], "nationality": ["China"],
      "birthPlace": ["Tianjin"]}),
]


@dataclass
class Work:
    zh_label: str
    en_label: str
    a_uri: str
    b_uri: str
    genre_zh: str
    genre_en: str
    year: int


@dataclass
class Entity:
    key: str                      # unique canonical key
    zh_label: str | None = None
    en_label: str | None = None
    a_uri: str | None = None
    b_uri: str | None = None
    facts_zh: dict = field(default_factory=dict)
    facts_en: dict = field(default_factory=dict)
    works: list = field(default_factory=list)
    core: bool = False

    def all_uris(self) -> list[str]:
        return [u for u in (self.a_uri, self.b_uri) if u]


@dataclass
class Bundle:
    graphs: dict
    entities: list
    total_triples: int


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def _cost(facts: dict, works: list) -> int:
    """Exact triples emitted for one entity in ONE graph.

    type + label, one triple per fact value, and 6 triples per work
    (type, label, genre, year, author, back-link).
    """
    n = 2
    for vals in facts.values():
        n += len(vals)
    n += 6 * len(works)
    return n


def _make_name(rng: random.Random, used: set) -> tuple[str, str]:
    while True:
        sn = rng.choice(list(SURNAME_PY))
        gv = rng.choice(list(GIVEN_PY))
        if rng.random() < 0.35:
            gv2 = rng.choice(list(GIVEN_PY))
            zh = sn + gv + gv2
            en = f"{SURNAME_PY[sn]} {GIVEN_PY[gv]}{GIVEN_PY[gv2]}"
        else:
            zh = sn + gv
            en = f"{SURNAME_PY[sn]} {GIVEN_PY[gv]}"
        if zh not in used:
            used.add(zh)
            return zh, en


def _make_en_name(rng: random.Random, used: set) -> str:
    """Western-style name with an optional middle initial -> ~10K combinations."""
    while True:
        first, last = rng.choice(EN_FIRST), rng.choice(EN_LAST)
        if rng.random() < 0.45:
            en = f"{first} {rng.choice(EN_MIDDLE)} {last}"
        else:
            en = f"{first} {last}"
        if en not in used:
            used.add(en)
            return en


def _person_facts(rng: random.Random, used: set | None = None) -> tuple[dict, dict]:
    by = rng.randint(1900, 2005)
    occup = rng.choice(ZH_OCCUP)
    city = rng.choice(ZH_CITY)
    fz = {"出生年份": [by], "职业": [occup[0]], "国籍": ["中国"], "出生地": [city[0]]}
    fe = {"birthYear": [by], "occupation": [occup[1]], "nationality": ["China"],
          "birthPlace": [city[1]]}
    if rng.random() < 0.35:
        dy = by + rng.randint(55, 92)
        fz["逝世年份"] = [dy]
        fe["deathYear"] = [dy]
    # A-only fact (pen name): no English counterpart, so an English query about
    # it can only be answered by crossing into Graph A. Pen names are kept
    # unique against real labels so a query naming one is not ambiguous.
    if rng.random() < 0.42:
        for _ in range(256):
            pen = rng.choice(list(SURNAME_PY)) + rng.choice(list(GIVEN_PY))
            if used is None or pen not in used:
                fz["别名"] = [pen]
                if used is not None:
                    used.add(pen)
                break
    # B-only fact (award): no Chinese counterpart, so a Chinese query about it
    # can only be answered by crossing into Graph B.
    if rng.random() < 0.42:
        award = rng.choice(AWARDS)
        fe["award"] = [f"{award} {rng.randint(1960, 2020)}"]
    return fz, fe


def build_dataset(target_triples: int = 50_000, seed: int = SEED) -> Bundle:
    """Build a two-graph store with approximately `target_triples` triples.

    Counts are calibrated by a cheap two-pass measurement rather than a guessed
    cost constant, so the realised size lands within ~2% of the requested
    scale for every operating point (10K / 50K / 100K / 200K).
    """
    bundle = _assemble(target_triples, seed, 1.0)
    ratio = target_triples / max(1, bundle.total_triples)
    if abs(ratio - 1.0) > 0.02:
        bundle = _assemble(target_triples, seed, ratio)
    log.info("Dataset @ target=%d -> A=%d B=%d total=%d | entities=%d",
             target_triples, len(bundle.graphs["A"]), len(bundle.graphs["B"]),
             bundle.total_triples, len(bundle.entities))
    return bundle


def _assemble(target_triples: int, seed: int, scale: float) -> Bundle:
    rng = random.Random(seed)
    entities: list[Entity] = []
    used_zh: set = set()
    used_en: set = set()

    # --- core -------------------------------------------------------------
    core_works = {c: w for c, w in CORE_WORKS}
    for zh, en, a_loc, b_loc, fz, fe in CORE_FACTS:
        works = []
        for wz, wa, wen, gz, ge, yr in core_works.get(zh, []):
            works.append(Work(wz, wen, str(KGA[wa]), str(KGB[wa]), gz, ge, yr))
        entities.append(Entity(
            key=zh, zh_label=zh, en_label=en, a_uri=str(KGA[a_loc]),
            b_uri=str(KGB[b_loc]), facts_zh=dict(fz), facts_en=dict(fe),
            works=works, core=True))
        used_zh.add(zh)
        used_en.add(en)
    for zh, a_loc, fz in CORE_A_ONLY:
        entities.append(Entity(key=zh, zh_label=zh, a_uri=str(KGA[a_loc]),
                               facts_zh=dict(fz), core=True))
        used_zh.add(zh)
    for en, b_loc, fe in CORE_B_ONLY:
        entities.append(Entity(key=en, en_label=en, b_uri=str(KGB[b_loc]),
                               facts_en=dict(fe), core=True))
        used_en.add(en)

    half_budget = max(200, target_triples // 2)
    core_cost = sum(_cost(e.facts_zh, e.works) for e in entities if e.zh_label)
    core_cost += sum(_cost(e.facts_en, e.works) for e in entities if e.en_label)
    per_graph_core = core_cost // 2

    # Average cost of the long-tail entity classes, measured from the class
    # itself rather than assumed, so the budget is filled to within ~1%.
    sample_pair = Entity("sample", facts_zh=_person_facts(rng)[0],
                         facts_en=_person_facts(rng)[1],
                         works=[Work("w", "w", "", "", "小说", "novel", 2000)])
    pair_cost = _cost(sample_pair.facts_zh, sample_pair.works)
    single_cost = _cost(_person_facts(rng)[0], [])

    # Allocation of the per-graph budget: 60% overlapping pairs, 20% A-only,
    # 20% B-only. A pair consumes `pair_cost` in BOTH graphs.
    remaining = max(0, half_budget - per_graph_core)
    n_pairs = max(80, int(remaining * 0.60 * scale / pair_cost))
    n_a_only = max(40, int(remaining * 0.20 * scale / single_cost))
    n_b_only = max(40, int(remaining * 0.20 * scale / single_cost))

    for i in range(n_pairs):
        zh, en = _make_name(rng, used_zh)
        guard = 0
        while en in used_en and guard < 64:
            zh, en = _make_name(rng, used_zh)
            guard += 1
        used_en.add(en)
        fz, fe = _person_facts(rng, used_zh)
        e = Entity(key=f"P{i:05d}", zh_label=zh, en_label=en,
                   a_uri=str(KGA[f"P{i:05d}A"]), b_uri=str(KGB[f"P{i:05d}B"]),
                   facts_zh=fz, facts_en=fe)
        # every long-tail person owns one work -> supports 2-hop queries
        gz, ge = rng.choice(GENRE)
        yr = rng.randint(1950, 2020)
        e.works.append(Work(f"作品{i}", f"Work {i}", str(KGA[f"W{i:05d}A"]),
                            str(KGB[f"W{i:05d}B"]), gz, ge, yr))
        entities.append(e)

    for i in range(n_a_only):
        zh, _en = _make_name(rng, used_zh)
        fz, _fe = _person_facts(rng, used_zh)
        entities.append(Entity(key=f"Q{i:05d}", zh_label=zh,
                               a_uri=str(KGA[f"Q{i:05d}A"]), facts_zh=fz))
    for i in range(n_b_only):
        en = _make_en_name(rng, used_en)
        _fz, fe = _person_facts(rng)
        entities.append(Entity(key=f"R{i:05d}", en_label=en,
                               b_uri=str(KGB[f"R{i:05d}B"]), facts_en=fe))

    # --- polysemy: duplicate surface labels with different identities -----
    n_homonym = max(8, int(len(entities) * 0.02))
    pool = [e for e in entities if not e.core and e.zh_label][:n_homonym]
    for j, base in enumerate(pool):
        fz, fe = _person_facts(rng, used_zh)
        # force a different birth year so the two namesakes are distinguishable
        fz["出生年份"] = [(int(base.facts_zh["出生年份"][0]) + 41) % 120 + 1880]
        fe["birthYear"] = fz["出生年份"]
        entities.append(Entity(key=f"H{j:05d}", zh_label=base.zh_label,
                               en_label=f"{base.en_label} II",
                               a_uri=str(KGA[f"H{j:05d}A"]),
                               b_uri=str(KGB[f"H{j:05d}B"]),
                               facts_zh=fz, facts_en=fe))

    graphs = _materialize(entities, rng)
    total = len(graphs["A"]) + len(graphs["B"])
    return Bundle(graphs=graphs, entities=entities, total_triples=total)


def _alt(pred: str, rng: random.Random, ratio: float = 0.18) -> str:
    """Schema-mismatch noise: sometimes emit a synonym predicate name."""
    if pred in ALT_PRED and rng.random() < ratio:
        return ALT_PRED[pred]
    return pred


def _materialize(entities: list[Entity], rng: random.Random) -> dict:
    ga, gb = Graph(), Graph()
    ga.bind("kgA", KGA), ga.bind("sx", SX)
    gb.bind("kgB", KGB), gb.bind("sy", SY)

    for e in entities:
        if e.a_uri:
            s = URIRef(e.a_uri)
            ga.add((s, RDF.type, PERSON_A))
            ga.add((s, RDFS.label, Literal(e.zh_label, lang="zh")))
            for pred, vals in e.facts_zh.items():
                p = SX[_alt(pred, rng)]
                for v in vals:
                    ga.add((s, p, Literal(v, datatype=XSD.integer)
                            if isinstance(v, int) else Literal(v)))
            for w in e.works:
                ws = URIRef(w.a_uri)
                ga.add((ws, RDF.type, WORK_A))
                ga.add((ws, RDFS.label, Literal(w.zh_label, lang="zh")))
                ga.add((ws, SX["体裁"], Literal(w.genre_zh)))
                ga.add((ws, SX["出版年份"], Literal(w.year, datatype=XSD.integer)))
                ga.add((ws, SX["作者"], s))
                ga.add((s, SX["代表作"], ws))
        if e.b_uri:
            s = URIRef(e.b_uri)
            gb.add((s, RDF.type, PERSON_B))
            gb.add((s, RDFS.label, Literal(e.en_label, lang="en")))
            for pred, vals in e.facts_en.items():
                p = SY[_alt(pred, rng)]
                for v in vals:
                    gb.add((s, p, Literal(v, datatype=XSD.integer)
                            if isinstance(v, int) else Literal(v)))
            for w in e.works:
                ws = URIRef(w.b_uri)
                gb.add((ws, RDF.type, WORK_B))
                gb.add((ws, RDFS.label, Literal(w.en_label, lang="en")))
                gb.add((ws, SY["genre"], Literal(w.genre_en)))
                gb.add((ws, SY["publicationYear"], Literal(w.year, datatype=XSD.integer)))
                gb.add((ws, SY["author"], s))
                gb.add((s, SY["notableWork"], ws))
    return {"A": ga, "B": gb}


# ---------------------------------------------------------------------------
# Lookups used by the runner
# ---------------------------------------------------------------------------
def merged_facts(e: Entity) -> dict[str, list[str]]:
    """canonical predicate local name -> string values, both schemas merged."""
    out: dict[str, list[str]] = {}
    for pred, vals in e.facts_zh.items():
        canon = ALT_LOOKUP.get(pred, pred)
        out.setdefault(canon, []).extend(str(v) for v in vals)
    for pred, vals in e.facts_en.items():
        canon = ALT_LOOKUP.get(pred, pred)
        out.setdefault(canon, []).extend(str(v) for v in vals)
    return out


ALT_LOOKUP = {v: k for k, v in ALT_PRED.items()}
for _k, (_zh, _en) in PRED.items():
    ALT_LOOKUP.setdefault(_zh, _zh)


def work_facts(e: Entity) -> dict[str, list[str]]:
    return {
        "体裁": [w.genre_zh for w in e.works] + [w.genre_en for w in e.works],
        "出版年份": [str(w.year) for w in e.works],
    }


def schema_predicates(graphs: dict) -> dict[str, int]:
    from engine import local_name
    return {name: len({local_name(str(p)) for p in g.predicates()})
            for name, g in graphs.items()}


# ---------------------------------------------------------------------------
# Simulated LLM parametric memory
# ---------------------------------------------------------------------------
def build_llm_memory(bundle: Bundle, coverage: float = 0.93,
                     seed: int = SEED) -> tuple[dict, dict, dict, dict]:
    """Reproduce what an LLM has memorised about this entity population.

    A real model knows most head entities and a shrinking fraction of the long
    tail. `coverage` is the fraction of entities whose cross-lingual mapping
    the simulated model remembers; the rest are genuine knowledge gaps.

    Returns (knowledge, label_to_key, alias_index, uri_graph).
    knowledge    : entity key -> normalised surface forms it can recall
    label_to_key : normalised label -> entity key (polysemous labels resolve
                   to the first owner, which is exactly how a memorised alias
                   table behaves)
    alias_index  : normalised label -> [(uri, graph)]
    uri_graph    : uri -> "A" / "B"
    """
    import zlib
    from engine import CandidateAnchorMapper as CAM

    norm = CAM.normalize
    label_to_key: dict[str, str] = {}
    alias_index: dict[str, list[tuple[str, str]]] = {}
    uri_graph: dict[str, str] = {}
    knowledge: dict[str, list[str]] = {}

    for e in bundle.entities:
        forms: list[str] = []
        for uri, graph, label in ((e.a_uri, "A", e.zh_label),
                                  (e.b_uri, "B", e.en_label)):
            if not uri:
                continue
            uri_graph[uri] = graph
            key = norm(label)
            alias_index.setdefault(key, []).append((uri, graph))
            # primary labels are authoritative; aliases only fill gaps
            label_to_key.setdefault(key, e.key)
            forms.append(key)
        # aliases are registered in a second pass so a pen name never
        # shadows another entity's real label in the LLM's memory
        for uri, graph, alias in ((e.a_uri, "A", e.facts_zh.get("别名", [None])[0]),
                                  (e.b_uri, "B", e.facts_en.get("alias", [None])[0])):
            if not uri or not alias:
                continue
            akey = norm(alias)
            alias_index.setdefault(akey, []).append((uri, graph))
            label_to_key.setdefault(akey, e.key)
            forms.append(akey)
        if (zlib.crc32(e.key.encode()) % 10_000) < coverage * 10_000:
            knowledge[e.key] = list(dict.fromkeys(forms))
    log.info("Simulated LLM memory: %d/%d entities memorised (coverage=%.0f%%)",
             len(knowledge), len(bundle.entities), 100 * coverage)
    return knowledge, label_to_key, alias_index, uri_graph
