# Day 02 交接总结

## 当前状态

仓库：`nuzhishen/day-002`

本地路径：

```text
C:\ai\day-002
```

GitHub：

```text
https://github.com/nuzhishen/day-002
```

当前分支：

```text
main
```

当前已推送提交：

```text
14c1bfe feat: phase0 day2 llm provider token budget prompts
```

## 已完成内容

### 上午部分

- Token 经济学文档。
- 上下文窗口、KV Cache、Lost in the Middle 说明。
- Temperature / Top_p 参数路由。
- `finish_reason` 状态机。
- Retry 分类决策表。
- Retry 随机 jitter。
- LLM 请求/响应 Pydantic 模型。
- Provider 抽象层、MockProvider、ProviderFactory。
- TokenBudget、TokenLedger、Pre-flight 预算拦截。

### 下午部分

- 3 个 System Prompt：
  - `app/prompts/tms_diagnosis.md`
  - `app/prompts/elderly_medication.md`
  - `app/prompts/ott_live_debug.md`
- 5 个 Mock 场景测试：
  - 正常调用。
  - 预算断路器。
  - `finish_reason=length`。
  - Retry 分类。
  - Prompt 注入合规检测。
- 合规率报告生成：
  - `docs/test_reports/day02_compliance.md`
- Token 成本统计报告：
  - `run_day02_reports.py`

### 晚间部分

- Day 2 模块说明。
- Token 成本控制面试话术。
- 晚间三问复盘。
- 验收报告。
- 文件变更清单。

## 核心代码入口

| 文件 | 作用 |
|---|---|
| `app/schemas/llm.py` | LLMRequest / LLMResponse / TokenUsage |
| `app/core/llm_provider.py` | Provider 抽象、MockProvider、Factory |
| `app/core/token_budget.py` | 预算、Ledger、日报 |
| `app/core/finish_reason.py` | 响应状态机 |
| `app/core/retry_policy.py` | Retry 分类与 jitter |
| `app/core/compliance.py` | Prompt 注入检测与合规报告 |
| `run_mock_demo.py` | Mock 调用演示 |
| `run_day02_reports.py` | 合规率与成本报告生成 |

## 验证命令

完整测试：

```powershell
cd C:\ai\day-002
.\.venv\Scripts\python.exe -m pytest -q
```

当前结果：

```text
31 passed
```

生成成本与合规报告：

```powershell
.\.venv\Scripts\python.exe run_day02_reports.py
```

当前输出：

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

## 设计决策

### finish_reason 状态机

最终实现不是“非 stop 一律异常”，而是：

```text
stop -> parse content
tool_calls -> validate tool name / args / permission / idempotency
length -> TruncationError -> compress / fallback / HITL
content_filter -> safety branch
unknown/null -> ProtocolError
```

原因：`tool_calls` 是 Agent 正常状态，不能误判为截断。

### Retry 边界

```text
429 -> 指数退避 + jitter，最多 3 次
500/502/503 -> 线性退避 + jitter，最多 2 次
timeout -> 1 次有限重试
400/401/403 -> 不重试
length -> 不原样重试，进入压缩/Fallback/HITL
content_filter -> 不重试，进入安全分支
```

### 预算策略

- 请求前使用 `estimated_cost_cents` 做 Pre-flight。
- 预算等于上限时也拦截，保留最小运行余量。
- 响应通过 `finish_reason` 校验后再扣费和记录 Ledger。

## 已知边界

- 当前不接真实 DeepSeek/Qwen API。
- 当前不引入 Redis。
- 当前不做真实分布式预算。
- 当前不写 ReAct 循环。
- 当前不做 RAG。
- 当前 Prompt 注入检测是最小规则版，只用于 Day 2 Mock 验证。
- `TokenLedger` 是内存实现，进程重启会丢失。

## 下一步建议

1. Day 3 若进入 LLM 调用封装，应新增真实 Provider 适配，但保持 Mock 测试不变。
2. 增加 HTTP 超时、API 错误码映射和失败注入。
3. 把 `TokenLedger` 扩展为可落库接口，但先保留内存实现。
4. 增加工具调用参数 Schema 校验，为后续 ReAct / Tool Calling 铺底。
5. 不要提前引入 RAG、LangGraph 或前端。

## 当前交接结论

Day 02 已完成训练令要求的 LLM 调用层、Token 预算、Retry 分类、`finish_reason` 校验、3 个业务 Prompt、5 个 Mock 场景、合规率报告和晚间复盘。当前代码可运行、可测试、已推送 GitHub，可作为 Day 3 的工程基础。

