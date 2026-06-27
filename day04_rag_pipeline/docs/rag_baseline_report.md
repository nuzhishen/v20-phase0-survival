# Day 4 RAG Baseline Report

- 生成时间：2026-06-27T20:30:22
- 运行方式：`python run_day04_eval.py`
- 默认链路：`MockEmbedding -> InMemoryVectorStore -> Retriever -> 8 metrics`
- 真实 Qdrant/BGE：通过 `run_day04_qdrant_smoke.py` 单独验证，避免单元测试依赖外部服务。

## 语料与评估集

- TMS chunk 数：10
- OTT chunk 数：10
- 养老健康 chunk 数：10
- 测试 Query 数：30
- 每条 Query 都包含 `expected_chunk_id`、`expected_keywords`、`ground_truth_context`、`ground_truth_answer`。

## 8 指标结果

| 指标 | Day 4 实测 | Day 4 基线 | 说明 |
|---|---:|---:|---|
| Recall@1 | 80.00% | >= 40.00% | Top1 是否命中预期 chunk |
| Recall@3 | 90.00% | >= 60.00% | Top3 是否命中预期 chunk |
| Recall@5 | 100.00% | >= 50.00% | Day 4 最核心检索基线 |
| MRR | 0.8678 | >= 0.6000 | 首个正确 chunk 越靠前越好 |
| Context Precision@5 | 94.00% | >= 60.00% | 按 AP@K 计算，相关证据越靠前越高 |
| No-answer/Fallback | 100.00% | >= 80.00% | 无关 query 应为空或低置信 |
| 低分率 | 3.33% | < 20.00% | Top score < 0.35 的比例 |
| 平均检索延迟 | 0.49 ms | < 200 ms | 本地 Mock + InMemory 基线 |

## 未 Top1 命中的 Query

| Query ID | 领域 | 预期 chunk | 实际 Top-K | 首中排名 | Top score |
|---|---|---|---|---:|---:|
| tms_002 | tms | tms_e1002 | tms_e1009, tms_e1002, tms_e1007, tms_e1008, tms_e1001 | 2 | 0.4832 |
| tms_004 | tms | tms_e1004 | tms_e1005, tms_e1008, tms_e1003, tms_e1007, tms_e1004 | 5 | 0.4168 |
| tms_010 | tms | tms_e1010 | tms_e1003, tms_e1010, tms_e1006 | 2 | 0.3637 |
| ott_004 | ott | ott_q004 | ott_q010, ott_q001, ott_q005, ott_q004, ott_q002 | 4 | 0.5354 |
| elderly_001 | elderly | elderly_001 | elderly_006, elderly_007, elderly_001 | 3 | 0.4534 |
| elderly_007 | elderly | elderly_007 | elderly_003, elderly_006, elderly_004, elderly_007, elderly_002 | 4 | 0.3190 |

## 结论

- Day 4 已完成 Dense Retrieval 基线，但这不是最终生产检索方案。
- MockEmbedding 只用于稳定测试，不声称等价于真实 BGE 语义质量。
- 纯 Dense 仍可能遇到语义鸿沟，Day 5 应用混合检索和 reranker 做对比实验。
- Qdrant 连接、HNSW 参数和 Payload 过滤已在源码中实现；API Key 通过环境变量读取，不写入仓库。
