# Day 02 LLM 调用层模块说明

## 模块目标

构建一个可测试的 LLM 调用抽象层，用 Mock 方式验证：

- 多模型 Provider 路由。
- 请求前预算预检。
- 响应后 `finish_reason` 校验。
- Token Ledger 记账。
- Retry 分类。
- Prompt 合规率报告。

## 核心文件

| 文件 | 说明 |
|---|---|
| `app/schemas/llm.py` | LLM 请求、响应和 usage 模型 |
| `app/core/llm_provider.py` | Provider 抽象、Mock 实现、Factory |
| `app/core/token_budget.py` | 内存预算、Ledger、成本报告 |
| `app/core/finish_reason.py` | stop/tool_calls/length/content_filter 状态机 |
| `app/core/retry_policy.py` | 可重试与不可重试决策 |
| `app/core/compliance.py` | 合规样例和报告渲染 |
| `app/prompts/*.md` | 3 个业务 System Prompt |

## 调用顺序

```text
LLMRequest
  -> ProviderFactory.get(model_name)
  -> TokenBudget.require_budget()
  -> MockProvider.chat_completion()
  -> classify_finish_reason()
  -> TokenBudget.charge()
  -> TokenLedger.record()
  -> LLMResponse
```

## 关键约束

- 预算预检失败时，Provider 不允许执行。
- `finish_reason=length` 不允许解析内容，不允许原样重试。
- `tool_calls` 是正常 Agent 状态，但必须校验工具名、参数、权限和幂等键。
- 429/5xx/timeout 可以有限重试；400/401/403/content_filter/length 不做原样重试。
- Prompt 注入检测当前是最小规则版，生产环境应替换为策略引擎。

## 运行

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run_day02_reports.py
```

