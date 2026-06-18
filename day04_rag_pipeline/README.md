# Day 04: Minimal RAG Pipeline

## 目标

独立跑通最小检索链路：

```text
文档加载 -> 切片 -> Embedding -> Qdrant Upsert -> Search -> Top-K
```

数据覆盖 TMS 运维手册、OTT FAQ 和养老健康指南。

## 必须完成

- 可重复的 Collection 配置。
- Chunk 元数据和来源标识。
- Top-K 检索结果包含证据来源。
- 30 条测试 Query 的基础评估数据。

## 禁止

- 不做 GraphRAG、多 Agent、复杂 Context Compression 或 RAG 平台。
- 不在本日加入 Reranker；Reranker 属于 Day 5。

