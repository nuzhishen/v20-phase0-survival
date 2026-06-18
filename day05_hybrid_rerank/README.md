# Day 05: Hybrid Retrieval and Rerank

## 目标

基于 Day 4 的同一批文档和 Query，对比：

```text
Dense only
vs
Dense + Sparse + Reranker
```

## 必须完成

- Dense/Sparse 权重可配置。
- Reranker 输入输出可测试。
- 使用相同评估集，避免实验口径变化。
- 输出命中率、Recall@K、延迟和失败样例对比报告。

## 禁止

- 不扩展为通用检索平台。
- 不为了指标引入与 Phase 0 无关的复杂模型链路。

