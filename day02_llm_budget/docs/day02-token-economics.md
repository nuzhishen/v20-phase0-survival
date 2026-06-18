# Day 02 Token 成本控制与面试话术

## 成本报表格式

```text
=== Day 02 Token Cost Report ===
Total Calls: 4
Total Prompt Tokens: 2400
Total Completion Tokens: 1200
Total Cost: 1.4 cents
Budget Remaining: 98.6 cents
Circuit Breaker Triggered: 1
Truncation Errors: 1
Compliance Rate: 80% (4/5)
```

## 三层防线

1. 请求前：估算输入、历史、工具 Schema 和最大输出成本。
2. 响应后：检查 `finish_reason`，禁止解析截断内容。
3. 失败时：按错误类型区分 Retry、Fallback、HITL。

## 30 秒话术

我今天实现了一个内嵌预算断路器和 `finish_reason` 校验的 LLM 调用层。它解决的是生产级 Agent 中的成本失控和截断崩溃问题。请求发出前先做 Token 预算预检，超限直接拦截；响应返回后先检查 `finish_reason`，`length` 立即抛 `TruncationError`，不解析残缺 JSON，也不原样重试；错误处理层区分 429、5xx、400、401 和截断场景，避免盲目重试。这个方案的权衡是增加少量调用层逻辑和配置维护成本，收益是把 LLM 调用从不可控消费行为变成可治理、可审计、可度量的工程资源。

## CTO 追问准备

为什么 `length` 不原样重试？

因为同样上下文和同样输出上限仍会截断，只会再次付费。正确做法是压缩上下文、裁剪工具 Schema、拆分任务或降级到规则引擎。

为什么预算等于上限也拦截？

因为生产系统需要保留最小运行余量。预算被打满后，后续安全告警、降级调用和审计动作都会失去余量。

