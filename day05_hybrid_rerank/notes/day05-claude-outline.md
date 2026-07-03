# Day 5 08:00-08:30 学习提纲

> 角色说明：原计划写作工具为 Claude Code；本仓库当前由 Codex 执行同等规划产物。08:30 之后的正式原理笔记按“手写笔记电子化整理”要求单独写入 `docs/day05-hybrid-reranker-notes.md`。

## 今日边界

Day 5 只在 Day 4 Dense Retrieval 基线上做可量化对比：

```text
Dense only
vs Sparse/BM25 only
vs Hybrid(Dense + Sparse)
vs Hybrid + Reranker
```

今日不做 Query Rewrite、GraphRAG、LangGraph、ReAct 深集成、前端、LLM 生成答案，也不改写 Day 4 baseline。所有实验复用 Day 4 的 30 条 Query 与同一批语料。

## 学习顺序

| 时间 | 主题 | 产出 |
|---|---|---|
| 08:00-08:30 | BM25、Hybrid、Reranker 学习规划 | 本提纲、公式推导步骤、追问清单 |
| 08:30-09:15 | BM25 / Sparse Retrieval | 写出 BM25 公式，解释 `TF`、`IDF`、`k1`、`b` |
| 09:15-10:00 | Dense vs Sparse | 从 6 个维度对比两类检索的适用边界 |
| 10:00-10:30 | Fusion | 写出 RRF、加权求和、线性插值三类融合公式 |
| 10:30-11:00 | Reranker | 对比 Bi-Encoder 与 Cross-Encoder，说明位置和成本 |

## 公式推导步骤

### 1. BM25

1. 从词项命中开始：query 由多个 term 组成，文档对 query 的得分是各 term 贡献之和。
2. 引入 `TF`：term 在文档里出现越多，贡献越高，但不能无限线性增长。
3. 引入 `k1`：控制 TF 饱和速度，`k1` 越大，词频增长越不容易饱和。
4. 引入 `b`：控制文档长度归一化，长文档不能只靠字多占便宜。
5. 引入 `IDF`：越稀有的 term 越有区分度，例如 `E1002`、`OTA_TIMEOUT`、`Android 5.5`。

### 2. Fusion

1. 先把 Dense 与 Sparse 看成两个不同检索器，各自返回候选与分数。
2. 如果分数尺度不一致，优先使用 RRF，因为它只依赖排名。
3. 如果分数已归一化，可用加权求和：`alpha` 控制 Dense 与 Sparse 占比。
4. 如果有验证集校准，可用线性插值或线性模型，让权重由实验数据决定。
5. Day 5 必须用 30 条 Query 做 alpha grid search，不拍脑袋固定权重。

### 3. Reranker

1. Retriever 的任务是从全库召回候选，不能太慢。
2. Bi-Encoder 预先编码文档，适合全库召回，速度快但交互弱。
3. Cross-Encoder 同时读取 query 与候选文本，判断更准但每个候选都要前向计算。
4. 因此 Reranker 只能排 TopN 候选，不能替代第一阶段检索。

## 面试追问清单

1. 为什么 Dense 不够？
   TMS 场景里错误码、设备型号、Android 版本、固件版本、日志枚举值都是精确符号，Dense 容易把它们语义化或稀释。

2. BM25 为什么还有价值？
   它对短文本、专有名词、错误码、版本号、精确术语可靠；只要词面命中，解释路径清晰。

3. Hybrid 权重怎么定？
   用 Day 4 的 30 条 Query 做 grid search，例如 `alpha=0.2/0.4/0.5/0.6/0.8`，比较 Recall、MRR、退化率和延迟。

4. RRF 为什么有用？
   RRF 基于排名融合，不要求 Dense score 与 BM25 score 在同一数值尺度上可比较。

5. Reranker 为什么不能替代检索？
   Cross-Encoder 成本高，只适合 TopN 精排；如果第一阶段没召回正确候选，Reranker 没东西可排。

6. 为什么今天不做 Query Rewrite？
   Rewrite 会引入新变量，污染 Dense vs Hybrid 的对比结论。今天先证明检索策略本身的增益。

7. 为什么今天不做 GraphRAG？
   Phase 0 目标是通关闭环和可解释对比，不是扩展复杂知识图谱。

## 今日一句话判断

在生产级 RAG 系统中，Dense Retrieval 不能单独承担全部召回，因为 TMS 场景存在大量错误码、设备型号、Android 版本和精确术语。我的设计选择是用 Dense 负责语义召回、Sparse/BM25 负责关键词召回，再通过 RRF 或 alpha 加权融合，并只对候选 TopN 做 Reranker 重排。代价是延迟和复杂度上升，收益必须用 Recall、MRR、退化率和延迟数据验证。
