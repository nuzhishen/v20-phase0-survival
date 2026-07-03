# Day 5 Hybrid Retrieval vs Dense Report

- 生成时间：2026-07-03T19:24:47
- 运行方式：`python -m app.rag.compare_eval`
- 语料：复用 Day 4 TMS / OTT / 养老健康 30 个 chunk。
- 评估集：复用 Day 4 `data/eval/rag_eval_queries.jsonl`，共 30 条 Query。
- TopK：5
- Candidate Pool：10
- Dense：Day 5 本地 MockDenseRetriever，保持 Day 4 MockEmbedding 的 n-gram/hash 口径。
- Sparse：本地 BM25，保留错误码、版本号、英文 token、数字和中文 n-gram。
- alpha 列表：0.2, 0.4, 0.5, 0.6, 0.8
- Reranker：BGE 未作为默认路径，使用 MockReranker 兜底，避免模型环境阻塞闭环。

## 指标对比

| Method | Recall@1 | Recall@3 | Recall@5 | Hit Rate@3 | MRR | Context Precision@5 | Avg Latency | Degrade vs Dense |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense Only | 80.00% | 90.00% | 100.00% | 90.00% | 0.8678 | 94.00% | 0.48 ms | 0.00% |
| Sparse BM25 Only | 96.67% | 100.00% | 100.00% | 100.00% | 0.9833 | 94.12% | 0.12 ms | 3.33% |
| Hybrid alpha=0.2 | 96.67% | 100.00% | 100.00% | 100.00% | 0.9833 | 95.61% | 0.66 ms | 3.33% |
| Hybrid alpha=0.4 | 96.67% | 100.00% | 100.00% | 100.00% | 0.9833 | 95.98% | 0.66 ms | 0.00% |
| Hybrid alpha=0.5 | 96.67% | 100.00% | 100.00% | 100.00% | 0.9833 | 95.88% | 0.66 ms | 0.00% |
| Hybrid alpha=0.6 | 96.67% | 100.00% | 100.00% | 100.00% | 0.9833 | 96.44% | 0.66 ms | 0.00% |
| Hybrid alpha=0.8 | 86.67% | 96.67% | 100.00% | 96.67% | 0.9194 | 95.59% | 0.66 ms | 0.00% |
| Hybrid RRF | 83.33% | 100.00% | 100.00% | 100.00% | 0.9167 | 95.14% | 0.65 ms | 0.00% |
| Best Hybrid + MockReranker (Hybrid alpha=0.6) | 100.00% | 100.00% | 100.00% | 100.00% | 1.0000 | 92.77% | 3.79 ms | 0.00% |

## 最优配置

- 最优 Hybrid：`Hybrid alpha=0.6`。
- 最终建议配置：`Best Hybrid + MockReranker (Hybrid alpha=0.6)`。
- Reranker 提升率：3.33%。
- Reranker Top1 提升率：3.33%。
- BGE-Reranker 状态：RuntimeError:BGE reranker is not configured in Day 5 default path。

选择规则：优先比较 `Recall@3`，再比较 `MRR`、`Recall@1`、`Context Precision@5` 和退化率。这符合 Day 6 的证据链需求：先保证正确证据进候选，再看排序质量。

## 失败 / 未提升样例

| Query ID | Domain | Expected | Dense Rank | Final Rank | Final TopK | 说明 |
|---|---|---|---:|---:|---|---|
| tms_001 | tms | tms_e1001 | 1 | 1 | tms_e1001, tms_e1010, tms_e1007, tms_e1004, tms_e1002 | 持平：没有相对 Dense 提升 |
| tms_003 | tms | tms_e1003 | 1 | 1 | tms_e1003, tms_e1004, tms_e1008, tms_e1002, tms_e1007 | 持平：没有相对 Dense 提升 |
| tms_005 | tms | tms_e1005 | 1 | 1 | tms_e1005, tms_e1003, tms_e1006, tms_e1001, tms_e1007 | 持平：没有相对 Dense 提升 |
| tms_006 | tms | tms_e1006 | 1 | 1 | tms_e1006, tms_e1004, tms_e1001, tms_e1007, tms_e1003 | 持平：没有相对 Dense 提升 |
| tms_007 | tms | tms_e1007 | 1 | 1 | tms_e1007, tms_e1002, tms_e1004, tms_e1010, tms_e1008 | 持平：没有相对 Dense 提升 |
| tms_008 | tms | tms_e1008 | 1 | 1 | tms_e1008, tms_e1004, tms_e1002, tms_e1007, tms_e1009 | 持平：没有相对 Dense 提升 |
| tms_009 | tms | tms_e1009 | 1 | 1 | tms_e1009, tms_e1002, tms_e1004, tms_e1003, tms_e1006 | 持平：没有相对 Dense 提升 |
| ott_001 | ott | ott_q001 | 1 | 1 | ott_q001, ott_q005, ott_q010, ott_q007, ott_q002 | 持平：没有相对 Dense 提升 |

## 30 秒面试话术

我今天在 Day4 Dense Retrieval 基线上实现了混合检索和 Reranker 对比实验。它解决的是单向量检索在 TMS 场景中对错误码、设备型号、Android 版本和精确术语召回不稳定的问题。我的方案是用 Dense 检索负责语义召回，用 Sparse/BM25 负责关键词和错误码召回，再通过 alpha 加权或 RRF 做融合，并在候选 TopN 上接入 Reranker 重排。

我没有拍脑袋固定权重，而是在 30 条 TMS/OTT/养老 Query 上跑了 alpha=0.2,0.4,0.5,0.6,0.8 和 RRF 的对比实验，并记录退化 Query。最终最优配置是 Best Hybrid + MockReranker (Hybrid alpha=0.6)，Recall@3 从 90.00% 变为 100.00%，MRR 从 0.8678 变为 1.0000，平均延迟变化 +3.32 ms。

这个方案的权衡是复杂度和延迟上升，但换来了更可解释的优化路径。如果 Hybrid 或 Reranker 没有提升，就按失败样例和退化率处理，不硬吹模型效果。周六通关测试应使用这套配置作为 RAG 检索层。

## 周六通关配置

- 检索配置：`Best Hybrid + MockReranker (Hybrid alpha=0.6)`。
- 接入方式：Day 6 只替换 Day 3 的 `lookup_error_knowledge()` 知识查询动作，不替换 ReAct 控制流。
- 安全边界：低置信、无结果或工具错误仍进入 Day 3 的 unknown / HITL / Observation 边界。
