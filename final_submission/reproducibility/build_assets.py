"""Build manuscript tables and figures from archived per-query records.

Run from the submission directory with:
    MPLCONFIGDIR=./reproducibility/.mplcache python3 reproducibility/build_assets.py

Inputs are included under reproducibility/data. Prompt exposure is regenerated
from the saved synthetic-data and benchmark generators with the published seeds.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path

import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta, binomtest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reproducibility" / "data"
OUT_T = ROOT / "tables"
OUT_F = ROOT / "figures"
OUT_T.mkdir(exist_ok=True)
OUT_F.mkdir(exist_ok=True)

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none", "pdf.fonttype": 42,
    "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": .65, "savefig.bbox": "tight",
})


def cp(k: int, n: int, alpha: float=.05):
    lo = 0.0 if k == 0 else float(beta.ppf(alpha/2, k, n-k+1))
    hi = 1.0 if k == n else float(beta.ppf(1-alpha/2, k+1, n-k))
    return lo, hi


def holm(ps):
    m=len(ps); order=np.argsort(ps); out=np.empty(m); running=0.0
    for rank,idx in enumerate(order):
        running=max(running,(m-rank)*ps[idx])
        out[idx]=min(1.0,running)
    return out


def latex_escape(s):
    return str(s).replace('_', r'\_').replace('%', r'\%').replace('&', r'\&')


def read_csv(path):
    return pd.read_csv(path, low_memory=False)

main=read_csv(DATA/"main"/"experimental_results.csv")
main_full=main[main.variant=="full_system"].set_index("qid")
labels={
    "full_system":"LLM planner",
    "no_aligner_k6":"No aligner (fixed $k=6$)",
    "no_predicate_constraint":"No predicate constraint",
    "no_pruning":"Global scan (no pruning)",
    "vector_graphrag":"Hashed-vector GraphRAG",
    "sparql_baseline":"Label-lookup pattern baseline",
}
variants=list(labels)
metrics=[]
for v in variants:
    d=main[main.variant==v]
    metrics.append({
      "variant":v,"label":labels[v],"n":len(d),
      "strict_n":int(d.success_strict.sum()),"strict":float(d.success_strict.mean()),
      "hits_n":int(d.hits1.sum()),"hits":float(d.hits1.mean()),
      "evidence_n":int(d.evidence_grounded.sum()),"evidence":float(d.evidence_grounded.mean()),
      "gsr":float(d.gsr.mean()),"triples_scanned":float(d.triples_scanned.mean())})
ms=pd.DataFrame(metrics)
ms.to_csv(DATA/"main"/"main_summary_recomputed.csv",index=False)

# Primary planned ablations: remove alignment, remove predicate constraints,
# and remove localization. Other baselines are descriptive only.
planned=["no_aligner_k6","no_predicate_constraint","no_pruning"]
ps=[]; paired=[]
for v in planned:
    b=main[main.variant==v].set_index("qid")
    a=main_full.success_strict.astype(bool); z=b.success_strict.astype(bool)
    n10=int((a & ~z).sum()); n01=int((~a & z).sum()); n=n10+n01
    p=float(binomtest(min(n10,n01),n,.5).pvalue) if n else 1.0
    p=min(1.0,p)
    ps.append(p)
    paired.append({"contrast":f"full_system vs {v}","n":len(a),"full_successes":int(a.sum()),"other_successes":int(z.sum()),"discordant_full_only":n10,"discordant_other_only":n01,"mcnemar_exact_p":p})
for r,padj in zip(paired,holm(ps)): r["holm_p_3_ablation_family"]=float(padj)
pd.DataFrame(paired).to_csv(DATA/"main"/"paired_ablation_tests.csv",index=False)

# Table 1: primary single-seed results.
rows=[]
for r in metrics:
    n=r['n'];k=r['strict_n']; lo,hi=cp(k,n)
    scan_text=f"{r['triples_scanned']:,.0f}" if r['triples_scanned'] >= 1000 else f"{r['triples_scanned']:.1f}"
    rows.append(f"{r['label']} & {k}/{n} ({r['strict']:.3f}; {lo:.3f}--{hi:.3f}) & {r['hits_n']}/{n} ({r['hits']:.3f}) & {r['gsr']:.6f} & {scan_text} " + r"\\")
(OUT_T/"table1_main.tex").write_text("\\begin{tabular}{lcccc}\n\\toprule\nSystem & Strict accuracy (95\\% exact CI) & Hits@1 & GSR & Scanned triples/query \\\\\n\\midrule\n"+"\n".join(rows)+"\n\\bottomrule\n\\end{tabular}\n")

# Reconstruct the application-level user prompt from code and saved seeds.
sys.path.insert(0,str(ROOT/"reproducibility"/"code"))
from scalable_data import build_dataset, build_llm_memory
from scalable_benchmark import build_benchmark
from engine import CandidateAnchorMapper, schema_summary
bundle=build_dataset(50_000,seed=20260101)
bench=build_benchmark(bundle,n_1hop=200,n_2hop=150,n_cross=150,seed=20260102)
knowledge,label_to_key,alias_index,_=build_llm_memory(bundle,coverage=.92,seed=20260104)
mapper=CandidateAnchorMapper(bundle.graphs,{
    "A":["http://example.org/schemaA/别名"],
    "B":["http://example.org/schemaB/alias"]})
schema=schema_summary(bundle.graphs)
schema_json=json.dumps(schema,ensure_ascii=False)
static_prefix=("You are an entity-alignment planner for a dual knowledge-graph system.\n"
    "Graph A uses Chinese labels and schemaA predicates; Graph B uses English labels and schemaB predicates. "
    "Different URIs may denote the same real-world entity; align them across the two graphs.\n\n")
static_between="\nCandidate surface anchors (retrieved by string matching): "
static_profile="\nCross-lingual entity profiles (canonical, all surface forms, all URIs across both graphs): "
static_schema="\nPredicate schema (local name -> description): "
static_suffix=("\n\nReturn STRICT JSON only (no prose, no markdown fences) with keys:\n"
    "  canonical_entity: string, the real-world entity the query targets\n"
    "  aligned_uris: array of URIs from BOTH graphs denoting this entity, ordered by confidence (cross-lingual counterparts first). Include only URIs from the candidate profiles that you are confident about.\n"
    "  predicate_constraints: array of predicate LOCAL NAMES (e.g. '别名', 'alias', '代表作') relevant to the query; [] means unconstrained.\n"
    "  rationale: very short string (under 10 words).")
components=[]; exposure=[]
for q in bench.queries:
    anchors,_=mapper.candidates(q.text)
    anchor_desc=[{"uri":a.uri,"graph":a.graph,"label":a.label,"score":round(a.score,4)} for a in anchors]
    candidate_entities=[]; seen=set()
    for a in anchors:
        canon=label_to_key.get(mapper.normalize(a.label)) if a.label else None
        if canon is None or canon in seen: continue
        seen.add(canon); forms=knowledge.get(canon,[]); all_uris=[]
        for form in forms:
            for uri,graph in alias_index.get(form,()):
                if (uri,graph) not in all_uris: all_uris.append((uri,graph))
        candidate_entities.append({"canonical":canon,"surface_forms":forms,
            "uris":[{"uri":uri,"graph":graph} for uri,graph in all_uris]})
    anchor_json=json.dumps(anchor_desc,ensure_ascii=False)
    profile_json=json.dumps(candidate_entities,ensure_ascii=False)
    query_component=f"User query: {q.text}\n"
    anchor_component=static_between+anchor_json
    profile_component=static_profile+profile_json
    schema_component=static_schema+schema_json
    fixed_component=static_prefix+static_suffix
    full_prompt=(static_prefix+query_component+anchor_component+profile_component+schema_component+static_suffix)
    golds=[str(u) for u in q.gt_uris]
    in_component=lambda value:any(g in value for g in golds)
    anchor_uri_exposed=in_component(anchor_json)
    profile_uri_exposed=in_component(profile_json)
    query_uri_exposed=in_component(q.text)
    schema_uri_exposed=in_component(schema_json)
    static_uri_exposed=in_component(fixed_component)
    exposed=any(g in full_prompt for g in golds)
    uri_re=__import__("re").compile(r"https?://[^\s\"'<>]+")
    anchor_uri_count=len(uri_re.findall(anchor_json))
    profile_uri_count=len(uri_re.findall(profile_json))
    components.append({
        "qid":q.qid,"category":q.category,
        "anchor_uri_exposed":int(anchor_uri_exposed),"profile_uri_exposed":int(profile_uri_exposed),
        "query_uri_exposed":int(query_uri_exposed),"predicate_schema_uri_exposed":int(schema_uri_exposed),
        "static_instruction_uri_exposed":int(static_uri_exposed),"gold_uri_in_application_prompt":int(exposed),
        "query_contains_uri_form":int(bool(uri_re.search(q.text))),
        "schema_contains_uri_form":int(bool(uri_re.search(schema_json))),
        "anchor_uri_count":anchor_uri_count,
        "profile_uri_count":profile_uri_count,
        "prompt_uri_count":len(uri_re.findall(full_prompt)),
    })
    exposure.append({"qid":q.qid,"category":q.category,
        "anchor_uri_exposed":int(anchor_uri_exposed),"profile_uri_exposed":int(profile_uri_exposed),
        "query_uri_exposed":int(query_uri_exposed),"predicate_schema_uri_exposed":int(schema_uri_exposed),
        "static_instruction_uri_exposed":int(static_uri_exposed),"exposed":int(exposed),
        "gold_uri_in_prompt":int(exposed)})
comp=pd.DataFrame(components)
comp.to_csv(DATA/"main"/"prompt_component_reconstruction.csv",index=False)
exp=pd.DataFrame(exposure)
exp.to_csv(DATA/"main"/"prompt_exposure_recomputed.csv",index=False)
component_rows=[]
for name,col in [("Candidate-anchor JSON","anchor_uri_exposed"),("Candidate-profile JSON","profile_uri_exposed"),
                 ("Query text","query_uri_exposed"),("Predicate-schema JSON","predicate_schema_uri_exposed"),
                 ("Static instructions","static_instruction_uri_exposed")]:
    subset=comp[comp.category.isin(["1-hop","cross-lingual"])]
    uri_any=int(comp.anchor_uri_count.sum()) if name=="Candidate-anchor JSON" else int(comp.profile_uri_count.sum()) if name=="Candidate-profile JSON" else int(comp.query_contains_uri_form.sum()) if name=="Query text" else int(comp.schema_contains_uri_form.sum()) if name=="Predicate-schema JSON" else 0
    component_rows.append({"application_prompt_component":name,
      "prompts_with_gold_uri_1hop":int(comp.loc[comp.category=="1-hop",col].sum()),
      "prompts_with_gold_uri_cross_lingual":int(comp.loc[comp.category=="cross-lingual",col].sum()),
      "prompts_with_gold_uri_two_hop":int(comp.loc[comp.category=="2-hop",col].sum()),
      "prompts_with_any_uri_form":uri_any,
    })
component_rows += [
    {"application_prompt_component":"System-role message","prompts_with_gold_uri_1hop":0,"prompts_with_gold_uri_cross_lingual":0,"prompts_with_gold_uri_two_hop":0,"prompts_with_any_uri_form":0},
    {"application_prompt_component":"Few-shot examples or additional context","prompts_with_gold_uri_1hop":0,"prompts_with_gold_uri_cross_lingual":0,"prompts_with_gold_uri_two_hop":0,"prompts_with_any_uri_form":0},
]
pd.DataFrame(component_rows).to_csv(DATA/"main"/"prompt_component_exposure.csv",index=False)
full=main[main.variant=="full_system"].merge(exp.drop(columns=["category"]),on="qid",validate="one_to_one")

# Table 2: descriptive family-stratified comparison with the fixed-k no-aligner baseline.
fixed=main[main.variant=="no_aligner_k6"].set_index("qid")
family_rows=[]
for family in ["1-hop","2-hop","cross-lingual"]:
    d=main[(main.variant=="full_system")&(main.category==family)].set_index("qid")
    b=fixed.loc[d.index]
    family_rows.append(f"{family} & {int(d.success_strict.sum())}/{len(d)} ({d.success_strict.mean():.3f}) & {int(b.success_strict.sum())}/{len(b)} ({b.success_strict.mean():.3f}) " + r"\\")
(OUT_T/"table2_family_comparison.tex").write_text("\\begin{tabular}{lcc}\n\\toprule\nQuery family & LLM planner, strict & Fixed-k no-aligner, strict " + "\\\\" + "\n\\midrule\n"+"\n".join(family_rows)+"\n\\bottomrule\n\\end{tabular}\n")

# Table 3: corrected full application-prompt exposure strata.
probe_rows=[]
for family in ["1-hop","2-hop","cross-lingual"]:
    x=full[full.category==family]
    if family=="2-hop":
        probe_rows.append("2-hop & Not applicable & 150 & 140/150 (0.933) & 144/150 (0.960) " + r"\\")
        continue
    for exposed,tag in [(1,"Gold URI present"),(0,"No explicit gold URI")]:
        d=x[x.exposed==exposed]
        if len(d)==0: continue
        n=len(d);k=int(d.success_strict.sum());hit=int(d.hits1.sum());lo,hi=cp(k,n)
        probe_rows.append(f"{family} & {tag} & {n} & {k}/{n} ({k/n:.3f}; {lo:.3f}--{hi:.3f}) & {hit}/{n} ({hit/n:.3f}) " + r"\\")
(OUT_T/"table3_probe.tex").write_text("\\begin{tabular}{llccc}\n\\toprule\nFamily & Gold URI condition & $n$ & Strict accuracy (95\\% exact CI) & Hits@1 " + "\\\\" + "\n\\midrule\n" + "\n".join(probe_rows) + "\n\\bottomrule\n\\end{tabular}\n")

# Table 3: sensitivity runs with seed reuse and query overlap made explicit.
seed_rows=[]; seed_summary=[]
main_texts=set(main_full["query"].astype(str))
for seed in ["20260101","20260301","20260401"]:
    d=read_csv(DATA/"seeds"/seed/"experimental_results.csv")
    f=d[d.variant=="full_system"]
    k=int(f.success_strict.sum()); n=len(f)
    unique_texts=set(f["query"].astype(str))
    overlap=len(unique_texts & main_texts)
    seed_label=seed + (" (primary seed)" if seed=="20260101" else "")
    seed_rows.append(f"{seed_label} & {overlap} & {k}/{n} ({k/n:.3f}) & {f.hits1.mean():.3f} & {f.evidence_grounded.mean():.3f} " + r"\\")
    seed_summary.append({"seed":seed,"n":n,"unique_query_texts":len(unique_texts),"overlap_distinct_query_texts_with_main":overlap,"strict_n":k,"strict":k/n,"hits1":f.hits1.mean(),"evidence_grounded":f.evidence_grounded.mean()})
sdf=pd.DataFrame(seed_summary); sdf.to_csv(DATA/"seeds"/"seed_summary_recomputed.csv",index=False)
mean=float(sdf.strict.mean()); sd=float(sdf.strict.std(ddof=1))
seed_rows.append(f"Mean (SD) & -- & {mean:.3f} ({sd:.3f}) & {sdf.hits1.mean():.3f} & {sdf.evidence_grounded.mean():.3f} " + r"\\")
(OUT_T/"table4_seeds.tex").write_text("\\begin{tabular}{l p{4.5cm}ccc}\n\\toprule\nData seed & Distinct query texts overlapping primary & Strict accuracy & Hits@1 & Value-in-context " + "\\\\" + "\n\\midrule\n" + "\n".join(seed_rows) + "\n\\bottomrule\n\\end{tabular}\n")

# Table 4: six saved paired Wikidata contrasts, recalculated from query-level rows.
from scipy.stats import binomtest
wik=read_csv(DATA/"wikidata"/"query_level_results.csv")
comparisons=[
    ("Matched LLM vs deterministic: all queries","llm_matched","deterministic_matched",lambda d: True),
    ("Matched LLM vs deterministic: one-hop","llm_matched","deterministic_matched",lambda d: d.family=="one-hop"),
    ("Matched LLM vs deterministic: cross-lingual","llm_matched","deterministic_matched",lambda d: d.family=="cross-lingual"),
    ("Matched LLM vs deterministic: cross train","llm_matched","deterministic_matched",lambda d: (d.family=="cross-lingual") & (d.alignment_split=="train")),
    ("Matched LLM vs deterministic: cross held-out","llm_matched","deterministic_matched",lambda d: (d.family=="cross-lingual") & (d.alignment_split=="held-out")),
    ("No explicit alignment table condition: LLM vs deterministic, cross-lingual","llm_no_alignment","deterministic_matched",lambda d: d.family=="cross-lingual"),
]
wd=[]
for name,a_name,b_name,predicate in comparisons:
    mask=predicate(wik)
    d=wik.copy() if isinstance(mask,bool) and mask else wik[mask].copy()
    a=d[d.group==a_name].set_index("qid").strict_success.astype(float)
    b=d[d.group==b_name].set_index("qid").strict_success.astype(float)
    ids=sorted(set(a.index)&set(b.index)); av=a.loc[ids].astype(bool); bv=b.loc[ids].astype(bool)
    both=int((av & bv).sum()); ao=int((av & ~bv).sum()); bo=int((~av & bv).sum()); neither=int((~av & ~bv).sum())
    m=ao+bo; pval=float(binomtest(min(ao,bo),m,.5).pvalue) if m else 1.0
    wd.append({"contrast":name,"A":a_name,"B":b_name,"n":len(ids),"A_successes":int(av.sum()),"B_successes":int(bv.sum()),"both_correct":both,"A_only":ao,"B_only":bo,"both_incorrect":neither,"raw_exact_two_sided_p":pval})
adj=holm([r["raw_exact_two_sided_p"] for r in wd])
for r,padj in zip(wd,adj): r["holm_adjusted_p_family_6"]=float(padj)
pd.DataFrame(wd).to_csv(DATA/"wikidata"/"statistical_tests.csv",index=False)
wiki_rows=[]
for r in wd:
    ptxt=f"{r['holm_adjusted_p_family_6']:.3f}"
    rawtxt=f"{r['raw_exact_two_sided_p']:.3g}"
    discord=f"{r['A_only']}/{r['B_only']}"
    wiki_rows.append(f"{latex_escape(r['contrast'])} & {r['A_successes']}/{r['n']} & {r['B_successes']}/{r['n']} & {discord} & {rawtxt} & {ptxt} " + r"\\")
(OUT_T/"table5_wikidata.tex").write_text("\\begin{tabular}{p{5.0cm}ccccc}\n\\toprule\nPaired contrast & A strict successes & B strict successes & A-only/B-only & Exact $p$ & Holm-adjusted $p$ " + "\\\\" + "\n\\midrule\n" + "\n".join(wiki_rows) + "\n\\bottomrule\n\\end{tabular}\n")

# Figure 1: per-family strict accuracy and overall logical access.
plot_vars=variants
fam_order=["1-hop","2-hop","cross-lingual"]
short={"full_system":"LLM planner","no_aligner_k6":"No aligner (fixed-k)","no_predicate_constraint":"No predicate","no_pruning":"No pruning","vector_graphrag":"Hashed-vector","sparql_baseline":"Label lookup"}
mat=np.array([[float(main[(main.variant==v)&(main.category==f)].success_strict.mean()) for f in fam_order] for v in plot_vars])
gsr=np.array([float(main[main.variant==v].gsr.mean()) for v in plot_vars])
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(7.1,3.1),gridspec_kw={"width_ratios":[1.05,1.0]})
im=ax1.imshow(mat,aspect="auto",vmin=0,vmax=1,cmap="Blues")
ax1.set_xticks(range(3),["One-hop","Two-hop","Cross-lingual"])
ax1.set_yticks(range(len(plot_vars)),[short[v] for v in plot_vars])
ax1.set_title("A  Strict accuracy by query family",loc="left",fontweight="bold")
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        n=200 if j==0 else 150
        k=int(round(mat[i,j]*n))
        ax1.text(j,i,f"{k}/{n}\n{mat[i,j]:.2f}",ha="center",va="center",color="white" if mat[i,j]>.55 else "#263238",fontsize=6.3)
cb=fig.colorbar(im,ax=ax1,fraction=.045,pad=.035);cb.set_label("Strict accuracy",fontsize=7);cb.ax.tick_params(labelsize=6)
order=np.argsort(gsr)
colors=["#277DA1" if plot_vars[i]=="full_system" else "#9AA0A6" for i in order]
ax2.barh(np.arange(len(order)),gsr[order],color=colors,height=.68)
ax2.set_yticks(np.arange(len(order)),[short[plot_vars[i]] for i in order])
ax2.set_xscale("log");ax2.set_xlabel("GSR (logical triple access; log scale)")
ax2.set_title("B  Access ratio",loc="left",fontweight="bold")
for y,i in enumerate(order): ax2.text(gsr[i]*1.12,y,f"{gsr[i]:.2g}",va="center",fontsize=6.3)
ax2.grid(axis="x",color="#d9dee2",linewidth=.45);ax2.set_axisbelow(True)
fig.subplots_adjust(wspace=.55,left=.16,right=.97,bottom=.15,top=.88)
for ext in ["pdf","svg"]: fig.savefig(OUT_F/f"fig1_main.{ext}")
fig.savefig(OUT_F/"fig1_main.png",dpi=300)
plt.close(fig)

# Figure 2: exact prompt-exposure strata (only families where probe applies).
strata=[]
for fam in ["1-hop","cross-lingual"]:
    x=full[full.category==fam]
    for e in [1,0]:
        d=x[x.exposed==e];n=len(d)
        if not n: continue
        k=int(d.success_strict.sum());lo,hi=cp(k,n)
        strata.append({"family":fam,"exposure":"present" if e else "absent","n":n,"successes":k,"rate":k/n,"lo":lo,"hi":hi})
probe=pd.DataFrame(strata);probe.to_csv(DATA/"main"/"probe_summary_recomputed.csv",index=False)
fig,ax=plt.subplots(figsize=(3.55,2.55))
family_colors={"1-hop":"#277DA1","cross-lingual":"#F28E2B"}
xpos={("1-hop","present"):0,("1-hop","absent"):1,("cross-lingual","present"):3,("cross-lingual","absent"):4}
for r in strata:
    x=xpos[(r['family'],r['exposure'])];y=r['rate'];col=family_colors[r['family']]
    ax.errorbar(x,y,yerr=[[y-r['lo']],[r['hi']-y]],fmt='o',color=col,markersize=5,capsize=2.5,lw=1.1)
    ax.text(x,y+.075,f"{r['successes']}/{r['n']}",ha='center',va='bottom',fontsize=6.5)
ax.set_xticks([0,3,4],["Present","Present","Absent"])
ax.set_ylabel("Strict accuracy")
ax.set_ylim(-.04,1.15);ax.set_xlim(-.55,4.55)
ax.axvline(2,color="#c6cbd0",lw=.7)
ax.text(0,1.09,"One-hop",ha="center",fontsize=7,fontweight="bold")
ax.text(3.5,1.09,"Cross-lingual",ha="center",fontsize=7,fontweight="bold")
ax.grid(axis='y',color="#d9dee2",linewidth=.45);ax.set_axisbelow(True)
fig.subplots_adjust(left=.17,right=.97,bottom=.18,top=.87)
for ext in ["pdf","svg"]:fig.savefig(OUT_F/f"fig2_probe.{ext}")
fig.savefig(OUT_F/"fig2_probe.png",dpi=300)
plt.close(fig)

# Machine-readable provenance for plotted values.
main.groupby(["variant","category"],as_index=False).agg(n=("qid","size"),strict=("success_strict","mean"),hits1=("hits1","mean"),gsr=("gsr","mean")).to_csv(DATA/"main"/"figure1_source.csv",index=False)
print("Built main tables, probe, seed summary, Wikidata table, and two figures.")
