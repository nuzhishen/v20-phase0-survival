# Day 4 晚间复盘与面试话术

## 1. 30 秒版本

我今天实现了一套去框架化的 RAG 检索底座，覆盖 `Load -> Chunk -> Embed -> Store -> Retrieve -> Evaluate`。语料包括 TMS 异常码、OTT FAQ 和养老健康指南，各 10 个 chunk；评估集是 30 条带 Ground Truth 的 Query。工程上使用三种切片器、EmbeddingProvider 抽象、Qdrant REST 客户端、HNSW 手写参数、domain Payload 过滤、Retriever latency 和低置信兜底。当前 Mock + InMemory 基线是 Recall@5 100.00%、Context Precision@5 94.00%、No-answer/Fallback 100.00%、平均检索延迟 0.49ms。它的价值是先建立可运行、可评估、可对比的检索基线；明天再用混合检索和 reranker 解决纯 Dense 的语义鸿沟。

## 2. 面试追问速答

### Q1：为什么 Day 4 不做 Generation？

因为生成会引入 LLM 随机性。Day 4 的目标是先证明“能不能找到正确证据”。如果检索都不稳定，LLM 生成得再流畅也无法证明答案可靠。

### Q2：Chunk size 怎么选？

不是先选固定数字，而是先看文档结构：

- TMS：异常码是天然边界，按 `## E1001` 段落切。
- OTT：FAQ 是一问一答，按 Q/A 对切。
- 养老健康：结构较弱，用固定长度但优先句界，避免切断血压范围、药品禁忌和异常处理。

### Q3：Qdrant 的 HNSW 参数怎么解释？

- `m=16`：每个节点最大连接数，值越大召回更好但内存更高。
- `ef_construct=100`：建图时搜索深度，值越大图质量更好但构建更慢。
- `hnsw_ef=64`：查询时搜索深度，值越大召回更高但延迟更大。
- `domain` payload index：先过滤领域，再做向量召回，避免 TMS/OTT/养老互相污染。

### Q4：为什么不用 LangChain/LlamaIndex？

Phase 0 的目标是理解并能解释核心链路。使用封装会隐藏 chunk、payload、HNSW、score threshold、fallback 的工程决策。今天必须手写这些边界，之后才有资格评估框架是否值得引入。

### Q5：语义鸿沟怎么解决？

Day 4 先记录纯 Dense 的失败样例。Day 5 用混合检索：

```text
Dense 向量负责语义相近
Sparse/BM25 负责精确词命中
Reranker 负责重新排序
```

例如用户说“直播卡顿”，文档可能写“OTT 播放延迟高”。Dense 可能命中，也可能被更泛化的播放故障干扰；BM25 可以补 `CDN`、`首帧`、`播放器版本` 这类精确词。

### Q6：为什么 128K 上下文仍需要 RAG？

长上下文不是免费数据库。它有三个问题：

- Token 成本高，TTFT 变慢。
- Lost in the Middle 会让关键证据被稀释。
- 没有检索评估，无法证明模型引用了正确知识。

RAG 的价值是把候选证据压缩到可解释、可评分、可回放的 Top-K。

### Q7：RAG 检索到了但 LLM 幻觉，责任怎么拆？

要分开评估：

- RAG 负责有没有找到正确证据，用 Recall@K、MRR、Context Precision 评估。
- LLM 负责有没有忠实使用证据，用 Faithfulness、Answer Relevancy 和人工审计评估。

Day 4 只测检索，避免把两个问题混在一起。

## 3. 今日数字

| 指标 | 当前值 |
|---|---:|
| Recall@1 | 80.00% |
| Recall@3 | 90.00% |
| Recall@5 | 100.00% |
| MRR | 0.8678 |
| Context Precision@5 | 94.00% |
| No-answer/Fallback | 100.00% |
| 低分率 | 3.33% |
| 平均检索延迟 | 0.49 ms |

数字来源：`docs/rag_baseline_report.md`，由 `run_day04_eval.py` 生成。

## 4. 未完成但刻意不做

| 项目 | 原因 |
|---|---|
| 混合检索 | Day 5 范围。 |
| Reranker | Day 5 范围。 |
| 真实 LLM 生成 | Day 4 只验证 Retrieval。 |
| GraphRAG | Phase 0 红线。 |
| Day 3 代码替换 | Day 6 集成范围，今天只准备接口和交接。 |

## 5. 明日最高优先级

1. 在同一份 30 Query 上跑 Dense only、Sparse only、Dense+Sparse 对照。
2. 记录未 Top1 样例是否被混合检索修复。
3. 引入 BGE-Reranker 前先固定 baseline，避免调参污染结论。
4. 准备 Day 6 把 TMS `lookup_error_knowledge()` 替换为 RAG Retriever 的最小接口。
