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

### 今天学到了什么？

### 今天什么没做出来？

## Day 6

### 今天做出来什么？

### 今天学到了什么？

### 今天什么没做出来？
