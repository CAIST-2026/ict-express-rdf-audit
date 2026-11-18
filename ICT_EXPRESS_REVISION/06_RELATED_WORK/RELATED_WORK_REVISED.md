# RELATED WORK REVISED

## Placement recommendation

ICT Express 短文不宜新增独立且冗长的 Related Work 节。建议在 Introduction 第一段之后加入下面一个紧凑段落（约 155 词），并在 Methods 的统计段保留 McNemar/Holm 引用。该段落只做定位与 gap statement，不重复后文结果。

## English draft

LLM--knowledge-graph integration is commonly motivated by the promise that a model can select relevant entities and relations before a structured store is queried. Roadmaps and GraphRAG-style systems situate this design within a broader move from static retrieval to model-guided graph access~\cite{pan2024unifying,lewis2020rag,edge2024graphrag}. Cross-lingual entity alignment provides a related but distinct capability: JAPE and subsequent benchmarks align entities across language-specific graphs, while recent LLM-based alignment work improves candidate selection with tailored prompts~\cite{sun2018jape,sun2020benchmark,yang2024segalign}. Multilingual dense retrieval offers another route to cross-language access through shared embedding spaces~\cite{karpukhin2020dpr,wang2024e5,zhang2023miracl}, and SPARQL 1.1 remains the standard declarative baseline over RDF~\cite{harris2013sparql}. Evaluation practice has likewise moved beyond final answers toward evidence-bearing judgements~\cite{thorne2018fever}. What these strands do not by themselves provide is a controlled test of attribution: when an LLM planner and a deterministic retriever receive the same alignment information, the same query workload, and the same literal-evidence criterion, how much accuracy remains attributable to the LLM? Our audit protocol targets precisely this gap rather than claiming a new alignment or retrieval architecture.

## Notes for paper revision

- 该段落明确区分三条路线：LLM-guided graph access、cross-lingual alignment、multilingual dense retrieval；避免把 GraphRAG 的端到端收益直接当作本文贡献。
- `edge2024graphrag` 是 arXiv preprint；若编辑偏好正式出版来源，可删除该引用而不影响论证。
- `barnett2024seven` 仍保留在 Introduction 第一段的 RAG failure points 论述中，但 DOI 与页码必须按核验表修正。
- 不要在 6 页正文里同时展开 mMARCO、best-practices、RAGAS 与 FEVER 的细节；它们作为证据谱系在补充材料中说明即可。
