# Phase 0 Daily Log

每天 21:00-23:00 回答三问。

## Day 1

### 今天做出来什么？

### 今天学到了什么？

### 今天什么没做出来？

## Day 2

### 今天做出来什么？

### 今天学到了什么？

### 今天什么没做出来？

## Day 3

### 今天做出来什么？

完成规则版最小 ReAct 状态机：

- `ReactState / ToolCall / ToolResult / DiagnosisResult` 类型定义。
- 5 个 TMS 异常码硬编码知识库。
- `ToolRegistry` 白名单和 4 个 Mock 工具。
- `run_react_loop()` 手写状态流转。
- 工具异常转 Observation，不让 Agent 崩溃。
- 未知异常码不胡编，进入人工排查。
- `max_steps=6` 和重复 Action 终止。
- HIGH 风险或批量操作触发 HITL。
- 10 条 TMS 样例评估，pytest 14 条通过。

### 今天学到了什么？

ReAct 不是 Prompt，而是状态机。生产级 Agent 必须显式控制 Thought、Action、Observation 和 Final，不能让模型自由决定是否查询证据、是否调用工具、是否跳过安全判断。

### 今天什么没做出来？

没有接真实 LLM，没有做 RAG，没有用 LangGraph，没有实现 Checkpoint / Retry / Circuit Breaker / DLQ。今天刻意只完成可控、可测、可审计的规则版状态机。

## Day 4

### 今天做出来什么？

### 今天学到了什么？

### 今天什么没做出来？

## Day 5

### 今天做出来什么？

完成 Day 5 Hybrid Retrieval + Reranker 对比实验：

- 复用 Day 4 的 30 条 Query 和语料，不覆盖 Day 4 Dense baseline。
- 实现本地 `MockDenseRetriever`，保持 Day 4 n-gram/hash 口径。
- 实现本地 BM25 Sparse，保留错误码、版本号、设备型号、英文 token、数字和中文 n-gram。
- 实现 Weighted、Linear、RRF 三种融合策略。
- 实现 `HybridRetriever` 统一入口。
- 实现 `MockReranker`、`BGEReranker` 占位和 `FallbackReranker`。
- 跑完 Dense、Sparse、5 组 alpha、RRF、Best Hybrid + MockReranker 对比。
- 生成 `hybrid_vs_dense_report.md` 和 `day05-what-blocked.md`。
- Day 5 单测 10 条通过，并纳入 Phase 0 总测试脚本。

### 今天学到了什么？

Dense 不能独立承担 TMS 场景全部召回，因为错误码、Android 版本、设备型号、CDN、NTP、403 等精确符号更适合 Sparse/BM25。Hybrid 权重不能拍脑袋，必须用同一评测集做 grid search。Reranker 只能重排候选 TopN，不能救回第一阶段没召回的正确 chunk。

### 今天什么没做出来？

没有把真实 BGE-Reranker 作为默认路径；当前默认使用 MockReranker 兜底。没有做 Query Rewrite、GraphRAG 或 ReAct 深集成，因为它们会污染 Dense vs Hybrid 对照实验或越过 Day 5 边界。Day 6 再负责把 Day 5 检索证据接入 Day 3 手写 ReAct 流程。

## Day 6

### 今天做出来什么？

### 今天学到了什么？

### 今天什么没做出来？
