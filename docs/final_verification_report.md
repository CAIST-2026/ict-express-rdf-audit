# 最终核查报告（交付物 7）

日期：本次会话 · 范围：`/Users/yuxiangsun/Desktop/ICT/ict_express_submission/`
原则：报告严格区分 **实际运行过的 / 复用的 / 未做的** 三类，不夸大。

---

## A. 本次实际运行并产出的（全部有 run_config.json + 逐查询 CSV）

| 实验 | 脚本 | 输出 | 关键结果 |
|---|---|---|---|
| 对齐监督探针 | `experiments/alignment_probe.py` | `results/main/alignment_probe/` | 跨语言查询 86.7% 金标在提示词内；Hits@1 = 0.500（在）vs 0.000（不在） |
| 公平基线 500 查询 | `experiments/baselines_ict.py` | `results/baselines/seed_20260101/`（per_query 2000 行） | sparql_real ac1 0.646（2-hop 0.900）；dense 0.544；translit 0.532；全部真实执行（1,500 次 rdflib SPARQL 调用） |
| 音译诊断 | `experiments/translit_diagnosis.py` | `results/diagnostics/` | translit 跨语言 0.307 = 二字名 46/46 全对、三字名 104/104 全为 0 —— 由生成器的姓名长度分布决定，不是模型能力 |
| 配对统计 | `experiments/stats_ict.py` | `results/stats/` | 全部对比 Holm 校正后 p<10⁻⁷；no_pruning 准确率 p=1（纯成本杠杆） |
| 三协议延迟 | `experiments/latency_ict.py`（24 查询×分层，含 4 warm-up） | `results/latency/` | full_system 串行 6,703 ms（LLM 占 99.99%）；4 并发 23,216 ms（排队）；traversal 0.19 ms vs no_pruning 47.1 ms |
| 规模扫描 | `experiments/scaling_ict.py`（10K/50K/100K/200K；LLM 变体 n=8，非 LLM 变体 n=100） | `results/scaling/` | GSR 的对数-对数斜率 −0.985 / −1.020（R²=0.9991 / 0.9991）；no_pruning 与 sparql_real 斜率 ≈0；sparql_real 延迟 63→1,250 ms（约 19.8×），full_system 稳定在 8.4–8.8 s（1.03×）；峰值内存 23.4→429.9 MB |
| 表格/图 | `experiments/summarize.py` | `tables/`、`figures/`、`traceability.csv` | 全部由脚本从 CSV 生成；追溯表 11 行覆盖论文中每个表格、图与摘要数字 |
| 论文编译 | `paper/main.tex`（cas-dc） | `paper/main.pdf`（4 页） | 编译干净；首页/表格/图已目检 |

## B. 复用的可信结果（未重跑）

- **主实验 500 查询 × 7 变体**（`rdf_llm_ea/outputs_audit/`，3,500 行）：已逐行核验
  （fallback 0/500、覆盖率 0.92、聚合与逐族数字与我的新指标重算一致）。不重跑。
- **多种子**（`outputs_seed_20260101/0301/0401`）、**覆盖率消融**（`outputs_cov100`）、
  **统计汇总**（`outputs_stats/`）：自洽，直接引用。**注意**：这三组用的是旧指标
  体系（`success_loose` / `success_strict`），与本报告的 `ac1` 不同定义，论文只在
  明确说明指标差异处引用，未与 `ac1` 混列。
- **旧规模部分数据**（`outputs_scaling/`）：仅作交叉参考，论文引用本次新跑。

## C. 未做（受资源/环境限制）及补跑命令

1. **更多种子下的公平基线**（本次基线仅 seed=20260101）。
   补跑：`baselines_ict.py --seed 20260301 --out results/baselines/seed_20260301`
2. **LLM 变体的多种子统计**：多种子结果属于旧指标体系（success_loose 等），
   严格的 ac1 未做多种子配对检验。补跑：对每个种子运行主实验后用 `stats_ict.py`。
3. **公开真实 RDF 数据验证**（如 DBP15K 只支持实体对齐子任务，无法验证端到端
   检索；本次未运行，论文未声称）。
4. **真实 ICT 场景数据**：不存在，论文已明确限制为合成基准。
5. **sentence-transformers**：沙箱无法安装；用 transformers 均值池化复现 e5-small
   （`dense_baseline.py` 已注释说明，编码输出已抽查）。
6. **人工标注一致性**：未做；论文相应声明 ac1/vic 为字符串匹配核验。

## D. 需作者确认的事项（见 README §7）

作者信息已填入（Yuxiang Sun，广州软件学院，通讯作者；Nan Yin，Canada
Advanced Institute of Science and Technology）。剩余：ORCID（可选）、
CRediT 实际分工确认、生成式 AI 声明的实际用途描述、参考文献
DOI/页码核对（尤其是 barnett2024seven）、 competing interest 工具输出、
**公开仓库的实际创建**（论文 Code and data availability 节承诺在录用后以
开放许可公开生成器/探针/基线/统计脚本与逐查询记录，投稿时补仓库 URL 与
存档 DOI——本目录即为可直接发布的起点，承诺必须兑现）。

## E. 合规检查

- 输入材料未改动（manuscript/、rdf_llm_ea/、audit/、elsarticle/ 均只读）。
- 未投稿、未实际公开发布代码（论文中的开源声明为承诺性文字，由作者在
  投稿/录用时兑现）、未向第三方发送任何材料。
- 论文无编造引用；数字全部可溯源（`traceability.csv`）。
- 格式：cas-dc（官方 Guide for Authors 当前推荐的 els-cas-templates；本地
  `elsarticle/` 为 2024 旧模板，仅作参考，未作为格式依据）。
- **5 页 ≤ 6 页上限**；摘要 ≈237 词 ≤250；关键词 5 个（1–7 之间）；7 个编号
  公式均经目检渲染正常。
- ICT Express 定位强化：Introduction 末段与 Conclusion "Implications for
  ICT systems" 段明确方法对基础设施元数据管理、跨域电信知识图谱集成、
  物联网异构检索三类场景的方法论指导意义。
