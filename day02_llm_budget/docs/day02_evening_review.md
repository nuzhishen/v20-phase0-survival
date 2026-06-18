# Day 02 晚间复盘

## 1. 今天做出来什么？

- LLMProvider 抽象层。
- ProviderFactory 模型路由。
- LLMRequest / LLMResponse / TokenUsage 数据模型。
- TokenBudget 内存预算断路器。
- TokenLedger 调用明细。
- `finish_reason` 状态机。
- Retry 分类决策树和 jitter。
- 3 个业务 System Prompt。
- 5 个 Mock 场景测试。
- 合规率报告。
- Token 成本报告。

## 2. 今天学到了什么？

LLM 调用不能被当成普通 HTTP 请求。生产级 Agent 必须在调用前控制预算，在响应后检查协议状态，并在失败时区分可重试、不可重试和必须降级的场景。尤其是 `finish_reason=length`，它不是普通失败，而是可能导致残缺 JSON、错误工具参数和状态污染的运行时事故。

## 3. 今天什么没做出来？

今天没有接真实 DeepSeek/Qwen API，也没有实现 Redis 分布式预算。这是刻意收敛：Phase 0 Day 2 的目标是先把调用层边界、预算、Retry 和合规统计跑通。明天如果进入真实模型调用，最高优先级是增加真实 Provider 适配、API 超时控制和 Token 估算器校准。

## 4. 明日最高优先级

1. 接入 Mock 之外的真实 Provider 适配层，但仍保持可替换。
2. 增加超时控制和失败注入。
3. 准备 ReAct 骨架前的 LLM 调用边界说明。

