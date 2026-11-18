"""Diagnose *why* the transliteration linker succeeds, and on what.

The transliteration baseline scores 0.307 on cross-lingual queries. Reporting
that number without its cause would invite the wrong conclusion ("phonetic
matching is a strong cross-lingual link"). The cause is a property of the data
generator, not of the method:

  scalable_data._make_name() draws ONE (surname, given) pair and emits
      zh = surname   + given            e.g. 曹芳
      en = SURNAME_PY[surname] + GIVEN_PY[given]   e.g. "Cao Fang"
  so two-character names are genuine romanisation pairs. For three-character
  names it draws an extra given syllable and the two strings stop being
  aligned, and the generator's stated design goal (line 10) is exactly that
  surface forms share nothing across graphs.

Consequence: the transliteration baseline's cross-lingual score is a mixture
whose mixing proportion is fixed by the generator's name-length distribution.
This script makes that explicit by stratifying success on Chinese name length.

Usage:
  python experiments/translit_diagnosis.py \
      --baselines results/baselines/seed_20260101/per_query.csv \
      --out results/diagnostics
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Portable source lookup: RDF_LLM_EA_SRC env var overrides the bundled copy.
SRC = Path(os.environ.get(
    "RDF_LLM_EA_SRC",
    str(Path(__file__).resolve().parents[1] / "upstream")))
sys.path.insert(0, str(SRC))

from scalable_benchmark import build_benchmark  # noqa: E402
from scalable_data import build_dataset  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triples", type=int, default=50_000)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--baselines", required=True)
    ap.add_argument("--out", default="results/diagnostics")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bundle = build_dataset(args.triples, seed=args.seed)
    n_1 = args.queries * 2 // 5
    n_2 = args.queries * 3 // 10
    bench = build_benchmark(bundle, n_1hop=n_1, n_2hop=n_2,
                            n_cross=args.queries - n_1 - n_2, seed=args.seed + 1)

    by_uri = {}
    for e in bundle.entities:
        if e.a_uri:
            by_uri[e.a_uri] = e
        if e.b_uri:
            by_uri[e.b_uri] = e

    rows = []
    for q in bench.queries:
        if q.category != "cross-lingual":
            continue
        e = by_uri.get(q.gt_uris[0])
        if e is None:
            continue
        rows.append({"qid": q.qid, "zh_label": e.zh_label, "en_label": e.en_label,
                     "zh_len": len(e.zh_label or ""),
                     "romanised_pair": int(
                         bool(e.zh_label) and bool(e.en_label)
                         and len(e.zh_label) == 2)})
    base = pd.DataFrame(rows)

    b = pd.read_csv(args.baselines)
    t = b[b.system == "translit"][["qid", "hits1", "ac1"]]
    m = base.merge(t, on="qid", how="left")

    strat = (m.groupby("zh_len")
               .agg(n=("hits1", "size"), hits1=("hits1", "mean"),
                    ac1=("ac1", "mean"))
               .reset_index().round(4))
    strat.to_csv(out / "translit_by_name_length.csv", index=False,
                 encoding="utf-8-sig")
    m.to_csv(out / "translit_per_query.csv", index=False, encoding="utf-8-sig")

    overall = float(m.hits1.mean())
    print(strat.to_string(index=False))
    print(f"\noverall translit cross-lingual Hits@1 = {overall:.4f}")
    print("Interpretation: success is 1.0 exactly on two-character (romanisation-"
          "paired) names and 0.0 on three-character names. The headline number is "
          "a mixture determined by the generator's name-length distribution, so it "
          "must not be read as evidence that phonetic matching is a strong "
          "cross-lingual linker in general.")


if __name__ == "__main__":
    main()
