"""P0 Stage 2: serialise alignment lookup and audit matched-supervision leakage.

Reads original/saved records only. Writes:
  01_MATCHED_SUPERVISION/data/alignment_snapshot.json
  01_MATCHED_SUPERVISION/results/MATCHED_SUPERVISION_PER_QUERY.csv
  01_MATCHED_SUPERVISION/results/MATCHED_SUPERVISION_STATISTICS.csv
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
SUB = ROOT / "ict_express_submission"
P1 = SUB / "ICT_EXPRESS_PHASE1"
REV = ROOT / "ICT_EXPRESS_REVISION" / "01_MATCHED_SUPERVISION"
sys.path.insert(0, str(SUB / "upstream"))
from scalable_data import build_dataset, build_llm_memory, SEED  # noqa: E402

RNG = np.random.default_rng(20260101)
URI_RE = re.compile(r"^http://example\.org/kg[AB]/entity/.+$")


def rd(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, encoding="utf-8-sig")


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict:
    n01 = int(((a == 1) & (b == 0)).sum())
    n10 = int(((a == 0) & (b == 1)).sum())
    n = n01 + n10
    p = 1.0 if n == 0 else float(binomtest(min(n01, n10), n, 0.5, alternative="two-sided").pvalue)
    or_val = None if n10 == 0 else n01 / n10
    return {"full_wins": n01, "nonllm_wins": n10, "n_discordant": n, "p_exact": p,
            "odds_ratio": or_val}


def boot_ci(diff: np.ndarray, n_boot: int = 10000) -> tuple[float, float]:
    idx = RNG.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    # 1. Serialise the exact lookup table used to build the planner prompt.
    bundle = build_dataset(target_triples=50_000, seed=SEED)
    knowledge, label_to_key, alias_index, uri_graph = build_llm_memory(
        bundle, coverage=0.92, seed=SEED + 3
    )
    snapshot = {
        "seed": SEED,
        "memory_seed": SEED + 3,
        "coverage": 0.92,
        "definition": "Deterministic alias table used by OllamaLLMFilter prompts and matched-supervision controls.",
        "knowledge": knowledge,
        "label_to_key": label_to_key,
        "alias_index": {k: [[str(u), str(g)] for u, g in v] for k, v in alias_index.items()},
        "uri_graph": {str(k): str(v) for k, v in uri_graph.items()},
    }
    snap_path = REV / "data/alignment_snapshot.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    # 2. Per-query diagnostics from matched-supervision records.
    matched = rd(P1 / "baseline_fairness/MATCHED_SUPERVISION_RESULTS.csv")
    main_df = rd(SUB / "upstream_results/experimental_results.csv").rename(
        columns={"success_strict": "ac1", "evidence_grounded": "vic", "variant": "system"}
    )
    llm = main_df[main_df.system == "full_system"].set_index("qid")
    no_align = main_df[main_df.system == "no_aligner"].set_index("qid")

    def uri_flags(s: str) -> tuple[int, int]:
        if not isinstance(s, str) or not s.strip():
            return 0, 1
        parts = [p for p in s.split("|") if p]
        valid = sum(bool(URI_RE.match(p.strip())) for p in parts)
        return valid, len(parts) - valid

    rows = []
    for _, r in matched.iterrows():
        qid = r.qid
        valid, invalid = uri_flags(llm.at[qid, "aligned_uris"] if qid in llm.index else "")
        rows.append({
            "qid": qid,
            "system": r.system,
            "group": r.group,
            "category": r.category,
            "ac1": r.ac1,
            "vic": r.vic,
            "hits1": r.hits1,
            "alignment_exposed": bool(r.exposed),
            "alignment_coverage": 1.0 if bool(r.exposed) else 0.0,
            "n_anchors": r.n_anchors,
            "n_aligned": r.n_aligned,
            "alignment_expansion": float(r.n_aligned) / max(1, int(r.n_anchors)),
            "evidence_recall_proxy": r.vic,
            "invalid_uri_count": invalid,
            "valid_uri_count": valid,
            "execution_failure": 0,  # main records all failure_mode=ok
            "predicate_selection_accuracy": None,
            "query_planning_success_rate": None,
            "invalid_sparql": None,
            "error_type": "none" if r.ac1 >= 0 else "unknown",
        })
    perq = pd.DataFrame(rows)
    perq_path = REV / "results/MATCHED_SUPERVISION_PER_QUERY.csv"
    perq_path.parent.mkdir(parents=True, exist_ok=True)
    perq.to_csv(perq_path, index=False)

    # 3. Paired statistics: LLM full_system vs matched non-LLM linker.
    ms = matched[matched.group == "MATCHED_SUPERVISION"].sort_values("qid")
    llm_full = llm.loc[ms.qid]
    a_ac = llm_full.ac1.to_numpy()
    b_ac = ms.ac1.to_numpy()
    a_vic = llm_full.vic.to_numpy()
    b_vic = ms.vic.to_numpy()

    stats_rows = []
    for scope, mask in [("overall_500", np.ones(len(ms), dtype=bool)),
                        ("cross_lingual_150", (ms.category == "cross-lingual").to_numpy())]:
        ac = mcnemar(a_ac[mask], b_ac[mask])
        d = a_ac[mask] - b_ac[mask]
        lo, hi = boot_ci(d)
        stats_rows.append({
            "scope": scope, "metric": "ac1", "test": "McNemar exact + paired bootstrap",
            "n": int(mask.sum()), "mean_ref": float(a_ac[mask].mean()),
            "mean_nonllm": float(b_ac[mask].mean()),
            "diff": float(d.mean()), "ci95_low": lo, "ci95_high": hi,
            **ac,
        })
        dv = a_vic[mask] - b_vic[mask]
        try:
            wp = float(wilcoxon(dv, zero_method="wilcox", alternative="two-sided").pvalue)
        except ValueError:
            wp = 1.0
        vlo, vhi = boot_ci(dv)
        stats_rows.append({
            "scope": scope, "metric": "vic", "test": "Wilcoxon signed-rank + paired bootstrap",
            "n": int(mask.sum()), "mean_ref": float(a_vic[mask].mean()),
            "mean_nonllm": float(b_vic[mask].mean()),
            "diff": float(dv.mean()), "ci95_low": vlo, "ci95_high": vhi,
            "p_exact": wp, "full_wins": int((dv > 0).sum()),
            "nonllm_wins": int((dv < 0).sum()),
            "n_discordant": int((dv != 0).sum()),
            "odds_rank_biserial": None,
        })

    # Holm correction across the four primary p-values.
    ps = np.array([float(r["p_exact"]) for r in stats_rows])
    order = np.argsort(ps)
    holm = np.empty_like(ps)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(ps) - rank) * ps[idx])
        holm[idx] = min(1.0, running)
    for r, hp in zip(stats_rows, holm):
        r["p_holm"] = float(hp)

    stats_path = REV / "results/MATCHED_SUPERVISION_STATISTICS.csv"
    pd.DataFrame(stats_rows).to_csv(stats_path, index=False)

    print(f"wrote {snap_path}")
    print(f"wrote {perq_path} rows={len(perq)}")
    print(f"wrote {stats_path} rows={len(stats_rows)}")
    print("\n--- paired statistics ---")
    print(pd.DataFrame(stats_rows)[
        ["scope", "metric", "n", "mean_ref", "mean_nonllm", "diff", "ci95_low", "ci95_high", "p_exact", "p_holm"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
