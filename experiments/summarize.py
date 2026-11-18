"""Build every paper table and figure from saved result files.

Nothing in the paper is typed by hand: each number in each table is produced
here from a CSV that an experiment wrote, and `traceability.csv` maps the paper
number back to (file, column, script). If a file is missing the corresponding
row is omitted rather than filled with a placeholder.

Inputs (all optional, but the run reports which were found):
  --main        outputs_audit/experimental_results.csv   (500 q x 7 variants)
  --baselines   results/baselines/<seed>/per_query.csv   (fair baselines)
  --latency     results/latency/per_query.csv
  --scaling     results/scaling/scaling.csv
  --seeds       outputs_seed_*/  outputs_cov100/
  --stats       outputs_stats/ (multi-seed summaries, if present)

Outputs: tables/*.tex (+ .csv), figures/*.pdf, traceability.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- style ----
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:                                        # pragma: no cover
    HAVE_MPL = False

# Chinese-market convention is NOT relevant here (papers use colour-blind safe
# palette); these are Okabe-Ito colours, safe for print and CVD.
C = {"main": "#0072B2", "sparql": "#D55E00", "dense": "#009E73",
     "translit": "#CC79A7", "vector": "#E69F00", "grey": "#666666"}

DISPLAY = {
    "full_system": "Localized (full)",
    "no_predicate_constraint": "\\quad $-$ predicate constraint",
    "no_pruning": "\\quad $-$ localized pruning",
    "no_aligner": "\\quad $-$ aligner",
    "no_aligner_k6": "\\quad $-$ aligner ($k{=}6$)",
    "vector_graphrag": "Vector-GraphRAG (legacy)",
    "sparql_baseline": "SPARQL (legacy, no engine)",
    "sparql_real": "SPARQL 1.1 (rdflib)",
    "dense": "Multilingual dense $+$ traversal",
    "dense_ne": "Multilingual dense (no traversal)",
    "translit": "Transliteration linker",
}
# shorter labels for the cramped main table
TABLE_DISPLAY = {
    "full_system": "Localized (full)",
    "no_predicate_constraint": "$-$ predicate constr.",
    "no_pruning": "$-$ localized pruning",
    "no_aligner": "$-$ aligner",
    "no_aligner_k6": "$-$ aligner ($k{=}6$)",
    "vector_graphrag": "Vector-GraphRAG$^{\\dagger}$",
    "sparql_baseline": "SPARQL$^{\\dagger}$ (no engine)",
    "sparql_real": "SPARQL 1.1 (rdflib)",
    "dense": "Dense e5 $+$ traversal",
    "dense_ne": "Dense e5 (no trav.)",
    "translit": "Transliteration",
}
ORDER = ["full_system", "no_predicate_constraint", "no_pruning", "no_aligner",
         "no_aligner_k6", "sparql_real", "sparql_baseline", "sparql_real",
         "dense", "dense_ne", "vector_graphrag", "translit", "sparql_baseline"]

CATS = ["1-hop", "2-hop", "cross-lingual"]
CAT_LAB = {"1-hop": "1-hop", "2-hop": "2-hop", "cross-lingual": "cross-ling."}


def _order(variants):
    seen, out = set(), []
    for v in ORDER + sorted(variants):
        if v in variants and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Bring the main run and the baseline runs onto one column schema."""
    d = df.copy()
    if "context_triples" in d.columns and "ctx_triples" not in d.columns:
        d = d.rename(columns={"context_triples": "ctx_triples"})
    if "success_strict" in d.columns:
        d = d.rename(columns={"success_strict": "ac1"})
    if "evidence_grounded" in d.columns and "vic" not in d.columns:
        d = d.rename(columns={"evidence_grounded": "vic"})
    if "variant" not in d.columns and "system" in d.columns:
        d = d.rename(columns={"system": "variant"})
    for c in ("hits1", "mrr", "ac1", "vic", "gsr", "ctx_triples", "category"):
        if c in d.columns:
            d[c] = (pd.to_numeric(d[c], errors="coerce")
                    if c != "category" else d[c])
    return d


# ------------------------------------------------------------- tables -----
def table_main(df: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Per-system accuracy + cost, overall and per family."""
    g = df.groupby("variant")
    rows = []
    for v in _order(set(g.groups)):
        d = g.get_group(v)
        row = {"system": v, "n": len(d),
               "hits1": d.hits1.mean(), "mrr": d.mrr.mean(),
               "ac1": d.ac1.mean(), "vic": d.vic.mean(),
               "gsr": d.gsr.mean(), "ctx": d.ctx_triples.mean()}
        for c in CATS:
            sub = d[d.category == c]
            row[f"ac1_{c}"] = sub.ac1.mean() if len(sub) else np.nan
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(out / "table1_main.csv", index=False, encoding="utf-8-sig")

    # NOTE: size/tabcolsep changes are wrapped in a group {...} so the font
    # size does NOT leak into the surrounding document text.
    lines = [r"{\setlength{\tabcolsep}{2.2pt}\scriptsize%",
             r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r"System & Hits@1 & $ac_1$ & $v_{ic}$ & GSR"
             r" & $ac_1$(1h) & $ac_1$(2h) & $ac_1$(xl) \\", r"\midrule"]
    prev = None
    for _, r in t.iterrows():
        name = TABLE_DISPLAY.get(r.system, r.system.replace("_", r"\_"))
        lines.append(
            f"{name} & {r.hits1:.3f} & {r.ac1:.3f} & "
            f"{r.vic:.3f} & {r.gsr:.1e} & "
            f"{r['ac1_1-hop']:.3f} & {r['ac1_2-hop']:.3f} & "
            f"{r['ac1_cross-lingual']:.3f} \\\\")
        prev = r.system
    lines += [r"\bottomrule", r"\end{tabular}}"]
    (out / "table1_main.tex").write_text("\n".join(lines), encoding="utf-8")
    return t


def table_probe(probe_csv: Path, out: Path) -> pd.DataFrame | None:
    if not probe_csv.exists():
        return None
    p = pd.read_csv(probe_csv)
    p.to_csv(out / "table2_probe.csv", index=False, encoding="utf-8-sig")
    lines = [r"{\setlength{\tabcolsep}{3pt}\small%",
             r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Query family & Alignment info & $n$ & Hits@1 & MRR & $ac_1$ \\",
             r"\midrule"]
    for _, r in p.iterrows():
        grp = {"gold_in_prompt": "in prompt", "gold_absent": "absent",
               "not_applicable": "n/a"}[r.group]
        lines.append(f"{CAT_LAB.get(r.category, r.category)} & {grp} & {int(r.n)} & "
                     f"{r.hits1:.3f} & {r.mrr:.3f} & {r.ac1:.3f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}}"]
    (out / "table2_probe.tex").write_text("\n".join(lines), encoding="utf-8")
    return p


def table_latency(lat: pd.DataFrame, out: Path) -> pd.DataFrame:
    keep = ["variant", "protocol", "workers", "n", "mean_ms", "median_ms",
            "p95_ms", "sd_ms", "qps", "mean_llm_ms", "mean_surface_ms"]
    t = lat[[c for c in keep if c in lat.columns]].copy()
    for c in ("mean_ms", "median_ms", "p95_ms", "sd_ms"):
        if c in t:
            t[c] = t[c].round(1)
    t.to_csv(out / "table3_latency.csv", index=False, encoding="utf-8-sig")

    # NOTE: size/tabcolsep wrapped in a group {...} so the font size does
    # NOT leak into the surrounding document text.
    lines = [r"{\setlength{\tabcolsep}{2.2pt}\scriptsize%",
             r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r"System & Protocol & $n$ & mean & median & P95 & SD & qps \\",
             r"\midrule"]
    for _, r in t.iterrows():
        name = DISPLAY.get(r.variant, r.variant.replace("_", r"\_"))
        proto = {"serial_service": "serial", "concurrent": "4-worker"}.get(
            r.protocol, r.protocol)
        lines.append(f"{name} & {proto} & {int(r.n)} & {r.mean_ms:.0f} & "
                     f"{r.median_ms:.0f} & {r.p95_ms:.0f} & {r.sd_ms:.0f} & "
                     f"{r.qps:g} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}}"]
    (out / "table3_latency.tex").write_text("\n".join(lines), encoding="utf-8")
    return t


def table_scaling(sc: pd.DataFrame, out: Path) -> pd.DataFrame:
    t = sc[["variant", "triples", "gsr", "hits1", "ac1", "mean_ms", "p95_ms",
            "ctx_triples", "peak_mb", "build_s", "protocol"]].copy()
    t.to_csv(out / "table4_scaling.csv", index=False, encoding="utf-8-sig")
    return t


def table_stats(pw: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Only the comparisons the paper actually claims something about.

    `stats_ict.py` emits one row per (contrast, metric) with mean_ref/mean_x,
    p_raw, p_holm and an effect size; pick the informative ones.
    """
    want = ["no_predicate_constraint", "no_pruning", "no_aligner",
            "sparql_real", "dense", "dense_ne", "translit",
            "vector_graphrag", "sparql_baseline"]
    rows = []
    for _, r in pw.iterrows():
        if r.get("metric") not in ("hits1", "ac1"):
            continue
        v = str(r.get("variant", ""))
        if v not in want:
            continue
        rows.append({"variant": v, "metric": r["metric"],
                     "n": int(r["n_pairs"]), "base": r["mean_ref"],
                     "variant_mean": r["mean_x"], "diff": r["diff"],
                     "p_raw": r["p_raw"], "p_holm": r["p_holm"],
                     "effect": r.get("effect", "")})
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t.to_csv(out / "table5_stats.csv", index=False, encoding="utf-8-sig")
    lines = [r"\begin{tabular}{llrrrrr}", r"\toprule",
             r"Contrast (vs.\ full) & Metric & $n$ & Full & Contrast & "
             r"$p_{\mathrm{Holm}}$ & OR \\", r"\midrule"]
    for _, r in t.iterrows():
        eff = r.effect
        eff = (f"{eff:g}" if isinstance(eff, (int, float)) and np.isfinite(eff)
               else "--")
        name = DISPLAY.get(r.variant, r.variant).replace("\\quad ", "")
        p = r.p_holm
        pstr = f"{p:.2g}" if p >= 1e-4 else r"$<$1e-4"
        lines.append(f"{name} & {r.metric} & {int(r.n)} & {r.base:.3f} & "
                     f"{r.variant_mean:.3f} & {pstr} & {eff} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "table5_stats.tex").write_text("\n".join(lines), encoding="utf-8")
    return t


# ------------------------------------------------------------ figures -----
def fig_accuracy(df: pd.DataFrame, out: Path) -> None:
    if not HAVE_MPL:
        return
    sysnames = [v for v in ("full_system", "sparql_real", "dense", "translit",
                            "vector_graphrag", "sparql_baseline") if v in set(df.variant)]
    if not sysnames:
        return
    labels = ["1-hop", "2-hop", "cross-ling."]
    cols = {"full_system": C["main"], "sparql_real": C["sparql"],
            "dense": C["dense"], "translit": C["translit"],
            "vector_graphrag": C["vector"], "sparql_baseline": C["grey"]}
    x = np.arange(len(labels))
    w = 0.8 / len(sysnames)
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    for i, v in enumerate(sysnames):
        d = df[df.variant == v]
        vals = [d[d.category == c].ac1.mean() for c in CATS]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w,
               label=DISPLAY.get(v, v).replace("\\quad ", ""),
               color=cols.get(v, C["grey"]), edgecolor="white", linewidth=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel(r"$ac_1$ (strict)", fontsize=7)
    ax.set_ylim(0, 1.05)
    ax.tick_params(labelsize=6)
    ax.legend(fontsize=5.2, frameon=False, ncol=2, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out / "fig2_accuracy.pdf")
    plt.close(fig)


def fig_probe(probe: pd.DataFrame, out: Path) -> None:
    if not HAVE_MPL:
        return
    d = probe[probe.category.isin(["1-hop", "cross-lingual"])]
    order = [("1-hop", "gold_in_prompt"), ("1-hop", "gold_absent"),
             ("cross-lingual", "gold_in_prompt"), ("cross-lingual", "gold_absent")]
    vals, labs, ns = [], [], []
    for cat, grp in order:
        r = d[(d.category == cat) & (d.group == grp)]
        vals.append(float(r.hits1.iloc[0]) if len(r) else 0.0)
        ns.append(int(r.n.iloc[0]) if len(r) else 0)
        labs.append(f"{CAT_LAB[cat]}\n{'in prompt' if grp == 'gold_in_prompt' else 'absent'}")
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    cols = [C["main"], C["grey"], C["main"], C["grey"]]
    bars = ax.bar(range(len(vals)), vals, color=cols, edgecolor="white", linewidth=0.5)
    for b, v, n in zip(bars, vals, ns):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}\n$n$={n}",
                ha="center", va="bottom", fontsize=5.6)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(labs, fontsize=5.6)
    ax.set_ylabel("Hits@1", fontsize=7)
    ax.set_ylim(0, 1.18)
    ax.tick_params(labelsize=6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out / "fig3_probe.pdf")
    plt.close(fig)


def fig_scaling(sc: pd.DataFrame, out: Path) -> None:
    if not HAVE_MPL:
        return
    d = sc[sc.gsr > 0]
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for v, g in d.groupby("variant"):
        if len(g) < 2:
            continue
        g = g.sort_values("triples")
        ax.plot(g.triples, g.gsr, "o-", ms=2.6, lw=1.0,
                color=C.get(v, C["grey"]), label=DISPLAY.get(v, v))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"store size $|T|$ (triples)", fontsize=7)
    ax.set_ylabel("GSR (logical access ratio)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.legend(fontsize=5, frameon=False, loc="best")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out / "fig4_scaling.pdf")
    plt.close(fig)


def fig_latency(lat: pd.DataFrame, out: Path) -> None:
    if not HAVE_MPL:
        return
    d = lat[lat.protocol == "serial_service"]
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    vs = [v for v in _order(set(d.variant)) if v in set(d.variant)]
    # log scale is essential: LLM latency is ~1e4 larger than traversal
    vals = [max(1e-3, float(d[d.variant == v].median_ms.iloc[0])) for v in vs]
    ax.barh(range(len(vs)), vals,
            color=[C["main"] if v == "full_system" else C["grey"] for v in vs],
            edgecolor="white", linewidth=0.4, height=0.62)
    ax.set_yticks(range(len(vs)))
    ax.set_yticklabels([DISPLAY.get(v, v).replace("\\quad ", "")
                        for v in vs], fontsize=5.6)
    ax.set_xscale("log")
    ax.set_xlabel("median service time (ms, log)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(out / "fig5_latency.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ main --
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default="")
    ap.add_argument("--baselines", default="")
    ap.add_argument("--probe", default="")
    ap.add_argument("--latency", default="")
    ap.add_argument("--scaling", default="")
    ap.add_argument("--stats", default="")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    root = Path(args.out)
    tdir, fdir = root / "tables", root / "figures"
    tdir.mkdir(parents=True, exist_ok=True)
    fdir.mkdir(parents=True, exist_ok=True)

    trace = []
    frames = []
    if args.main and Path(args.main).exists():
        d = _normalise(pd.read_csv(args.main))
        frames.append(d)
        trace.append({"paper_item": "Table 1 (main systems)",
                      "file": args.main, "columns": "hits1,mrr,ac1,vic,gsr",
                      "script": "experiments/summarize.py"})

    if args.baselines and Path(args.baselines).exists():
        b = _normalise(pd.read_csv(args.baselines))
        frames.append(b)
        trace.append({"paper_item": "Table 1 (fair baselines)",
                      "file": args.baselines, "columns": "hits1,mrr,ac1,vic,gsr",
                      "script": "experiments/baselines_ict.py"})

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not df.empty:
        table_main(df, tdir)
        fig_accuracy(df, fdir)

    if args.probe and Path(args.probe).exists():
        p = table_probe(Path(args.probe), tdir)
        if p is not None:
            fig_probe(p, fdir)
            trace.append({"paper_item": "Table 2 / Fig. 3 (alignment probe)",
                          "file": args.probe,
                          "columns": "category,group,n,hits1,mrr,ac1",
                          "script": "experiments/alignment_probe.py"})

    if args.latency and Path(args.latency).exists():
        lat = pd.read_csv(args.latency)
        table_latency(lat, tdir)
        fig_latency(lat, fdir)
        trace.append({"paper_item": "Table 3 / Fig. 5 (latency)",
                      "file": args.latency,
                      "columns": "protocol,mean_ms,median_ms,p95_ms,qps",
                      "script": "experiments/latency_ict.py"})

    if args.scaling and Path(args.scaling).exists():
        sc = pd.read_csv(args.scaling)
        table_scaling(sc, tdir)
        fig_scaling(sc, fdir)
        trace.append({"paper_item": "Table 4 / Fig. 4 (scaling)",
                      "file": args.scaling,
                      "columns": "triples,gsr,hits1,ac1,mean_ms,peak_mb",
                      "script": "experiments/scaling_ict.py"})

    if args.stats and Path(args.stats).exists():
        pw_path = Path(args.stats)
        if pw_path.is_dir():
            pw_path = pw_path / "pairwise_tests.csv"
        if pw_path.exists():
            pw = pd.read_csv(pw_path)
            table_stats(pw, tdir)
            trace.append({"paper_item": "Table 5 (paired tests)",
                          "file": str(pw_path),
                          "columns": "p_value,p_holm,odds_ratio",
                          "script": "experiments/stats_ict.py"})

    pd.DataFrame(trace).to_csv(root / "traceability.csv", index=False,
                               encoding="utf-8-sig")
    print(f"tables -> {tdir}")
    print(f"figures -> {fdir}")
    print(f"traceability rows: {len(trace)}")


if __name__ == "__main__":
    main()
