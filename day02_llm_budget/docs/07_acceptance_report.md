# Day 2 完整验收报告

## 验收范围

上午部分：

- Token 消耗分布图。
- KV Cache、Lost in the Middle、上下文膨胀说明。
- Temperature/Top_p 决策矩阵。
- `finish_reason` 状态机。
- Retry 分类决策表与 jitter。
- LLM 数据模型、Provider Factory、预算、Ledger 基础代码。

下午部分：

- 3 个业务 System Prompt。
- 5 个 Mock 场景测试。
- Prompt 注入最小合规检测。
- 合规率报告。
- 成本统计报告。

晚间部分：

- 30 秒面试话术。
- 三问复盘。
- Day2 模块说明。
- 变更清单。

## 关键设计修正

原计划中的“非 stop 一律抛 TruncationError”不可直接执行，因为 `tool_calls` 是正常 Agent 状态。最终实现按状态分类：

```text
stop -> parse
tool_calls -> validate tools
length -> TruncationError
content_filter -> safety branch
unknown -> ProtocolError
```

## 测试

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
31 passed in 0.20s
```

覆盖：

- 2400 Token 分布与隐藏开销。
- 输入/输出分价成本计算。
- Pre-flight 预算拦截。
- `stop/tool_calls/length/content_filter/unknown` 状态。
- 429、503、400、401、403、超时和截断 Retry 分类。
- 三类任务参数路由。
- Provider Factory、Mock 调用、预算扣费与 Ledger。
- 5 个 Day2 Mock 场景。
- 合规率报告。
- 每日成本报告。

## 报告脚本

执行：

```powershell
.\.venv\Scripts\python.exe run_day02_reports.py
```

输出：

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

