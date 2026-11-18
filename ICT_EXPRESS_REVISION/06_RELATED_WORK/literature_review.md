# Related-work evidence map

## 1. Scope and method

本文件服务于 WorkBuddy 修订任务的 Stage 7。检索目标是回答一个比“有没有相关工作”更严格的问题：**现有工作是否已经解决了本文所审计的具体混淆**，即（i）LLM 与传统检索器是否在相同对齐监督下比较；（ii）答案判定是否独立于生成模型；（iii）跨语言 RDF 检索是否区分“语言内规划”“跨图对齐”“证据抽取”；（iv）延迟是否在同一查询负载下测量。

核验来源限定为出版方页面、ACL Anthology、arXiv 摘要页、W3C 标准页或权威索引记录。逐条结果见 `REFERENCE_VERIFICATION.csv`，BibTeX 见 `references.bib`。核验中发现当前论文有两处 DOI 错误，必须在论文修订阶段修正：

- `pan2024unifying`：当前稿写 `10.1109/TKDE.2024.3305490`，正确为 `10.1109/TKDE.2024.3352100`。
- `barnett2024seven`：当前稿写 `10.1145/3726302.3730130` 且页码 1--5，正确为 `10.1145/3644815.3644945` 且页码 194--199。

## 2. Five literature strands

### 2.1 LLM--KG integration and GraphRAG

Pan et al. 的 roadmap 将 LLM--KG 工作分为 KG-enhanced LLM、LLM-augmented KG 与二者协同三类；Lewis et al. 建立了通用 RAG 框架；Edge et al. 的 GraphRAG 将图索引与社区摘要引入生成式问答。这些工作说明“把 LLM 放进检索/推理回路”是主流方向，但通常报告端到端收益，而不是把 LLM 的规划贡献与检索器获得的监督信息分离。本文因此不重新论证 GraphRAG 有效，而是审计其增益来源。

### 2.2 Cross-lingual entity alignment

JAPE/DBP15K 与 PVLDB 基准确立了 embedding-based entity alignment 的标准评测；Seg-Align 进一步用 LLM 做跨语言实体对齐。关键差异是：这些任务把“找到对齐实体”本身作为目标，通常提供种子对齐或构造好的候选集；本文的 RDF 检索任务中，对齐信息可能已经出现在 planner prompt 的 entity profile 里。若不显式记录 gold URI 是否暴露，LLM 的“对齐成功”会被高估。现有 entity-alignment 文献并不自动消除这一 prompt-level leakage。

### 2.3 Multilingual dense retrieval

DPR 奠定 dense passage retrieval；mMARCO、多语言 dense retrieval best-practices 与 MIRACL 将评测扩展到多语言。E5 提供了可公开使用的多语言句向量模型。因此，用一个 monolingual hashed encoder 作为强基线是不充分的；本文已加入 multilingual E5 + traversal。但 dense retrieval 主要通过语义相似度跨越语言差异，不能等价于跨图 URI identity 对齐，也不能保证 predicate-level evidence 落在 retrieved context 中。这是本文采用 judge-free `ac1` 而非仅看 Hits@1 的原因。

### 2.4 RDF/SPARQL retrieval

SPARQL 1.1 是 RDF 查询的标准基线；Wikidata 提供真实、多语言、CC0 的 RDF/知识图谱验证资源。LLM-to-SPARQL 工作关注自然语言到查询的生成，而本文关心给定自然语言问题后，真实 SPARQL 执行、localized traversal 与 LLM planner 在同等输入下的准确率与成本。原稿中的“SPARQL”假基线必须替换为真实 `Graph.query` 执行，否则基线名称会造成误导。

### 2.5 Evidence-grounded and judge-free evaluation

FEVER 将“声明 + 证据”作为事实核验对象；RAGAS 提出自动化 RAG 评测维度。它们共同支持“不能只看最终自然语言答案”的观点。本文进一步把证据限定为可机器核对的 RDF 三元组：`ac1` 要求 gold entity 排第一且 gold value 字面出现在 evidence triples 中，`vic` 只要求值出现。这样避免让同一个 LLM 既生成答案又当 judge，也避免 judge-proxy bias。

## 3. Gap statement

现有文献分别覆盖了图中的 LLM 规划、跨语言对齐、多语言稠密检索、RDF 查询与证据评测，但本文所需的控制条件并不由任何单一文献提供：让 LLM planner、deterministic traversal、real SPARQL 与 dense retriever 在同一查询负载、同一对齐表、同一证据判定规则下比较，并显式记录 prompt 中 gold URI 的可见性。本文的方法论贡献应定位为**审计协议与受控评测设计**，而不是提出新的 GraphRAG 架构或声称解决了跨语言实体对齐。

## 4. 6 页篇幅下的引用优先级

若正文只保留 8--12 条引用，优先级建议：

1. 必引：`pan2024unifying`、`barnett2024seven`、`sun2018jape`、`yang2024segalign`、`wang2024e5`、`harris2013sparql`、`thorne2018fever`。
2. 若 method/baseline 段有空间：补 `lewis2020rag`、`karpukhin2020dpr`、`zhang2023miracl`、`vrandecic2014wikidata`。
3. 统计引用 `mcnemar1947`、`holm1979` 保留在 Methods/Statistics 段，不以扩展 Related Work 为名堆叠。
4. `bonifacio2021mmarco`、`zhang2022bestpractices`、`edge2024graphrag`、`sun2020benchmark`、`es2023ragas` 作为 background 候选，按版面取舍。

不要为了增加引用数而加入未核验或无法在 6 页内讨论的文献。
