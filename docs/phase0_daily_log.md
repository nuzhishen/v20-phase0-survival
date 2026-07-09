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

完成 Phase 0 Day6 Survival Gate：

- 在 `day06_pass_test/` 内实现最小 Agent Runtime 闭环：`DeviceIssueQuery -> RAG -> ReAct -> Tool -> DiagnosisResult`。
- 读取 Day4 TMS 手册，在 Day6 内实现 Day5 风格的 Dense + Sparse + Hybrid alpha=0.6 + MockReranker 检索策略。
- 实现 L1-L4 降级：Hybrid+Reranker、Hybrid、Dense、规则知识库。
- 实现 Day3 风格规则版 ReAct 状态机，保留 `max_steps=6`、工具白名单、重复 Action 终止、未知码兜底、工具异常 Observation、HITL。
- 实现 4 个 Mock 工具：`query_device_status`、`query_ota_history`、`estimate_batch_risk`、`should_require_hitl`。
- 固化 10 条通关样例，覆盖 OTA_TIMEOUT、DEVICE_OFFLINE、FIRMWARE_MISMATCH、HIGH_FAILURE_RATE、SCRIPT_EXEC_ERROR、UNKNOWN_CODE、RAG 无结果、工具异常、大批量 HITL、OTT 跨域拒绝。
- 生成 `day06-survival-gate-report.md`、`day06-elimination-review.md`、`day06-demo-script.md`、`day06-architecture.md`。
- Day6 单测 `9 passed`，Phase 0 总回归 Day1-Day6 全部通过。

### 今天学到了什么？

Agent 能力不是单点 Prompt、单点 RAG 或单点工具调用，而是链路可靠性。RAG 只提供证据，不能绕过 ReAct 的安全判断；工具异常必须转 Observation；高风险和大批量操作必须 HITL；fallback 必须显式暴露在结果里。

今天的关键判断是：通关日不要继续调检索，也不要引入 LangGraph/MCP/Redis 等新变量。先用规则版状态机证明最小 Runtime 的可运行、可测试、可解释，再进入 P1 做 Checkpoint、Retry、Circuit Breaker、DLQ、幂等和队列。

### 今天什么没做出来？

没有接真实 LLM、真实 Qdrant、真实 BGE-Reranker、真实 OTA、真实脚本或真实重启。没有实现并发队列、幂等、Checkpoint、Retry、Circuit Breaker、DLQ 或成本预算。这些不属于 Phase 0 Day6，后续进入 P1 正式项目再做。

Day6 的 10 条样例全部通过，但 N=10 只是通关裁定，不是生产统计显著性。生产级指标需要 P1 后续扩大评估集和故障注入。
