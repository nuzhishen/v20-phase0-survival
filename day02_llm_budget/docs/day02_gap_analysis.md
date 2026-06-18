# Day 2 差距判断

## 上午部分完成度

已完成：

- `LLMRequest / LLMResponse / TokenUsage` Pydantic 模型。
- `LLMProvider` 抽象基类、`MockProvider`、`ProviderFactory`。
- `TokenBudget` 内存预算、Pre-flight 拦截、扣费。
- `TokenLedger` 调用明细记录。
- `finish_reason` 状态机。
- Retry 分类决策，包含 429/5xx/400/401/403/timeout/length。
- Retry jitter。
- Token 经济学、上下文窗口、采样参数、面试攻击点文档。

上午缺口，本次已补齐：

- 计划指定的 `tests/test_llm_day02.py` 综合验收文件。
- `TokenBudget.generate_daily_report()` 成本报告接口。
- `format_daily_report()` 控制台格式化输出。

## 下午/晚间缺口，本次已补齐

- 3 个业务 System Prompt。
- 5 个 Mock 场景自动化测试。
- Prompt 注入最小合规检测。
- 合规率报告渲染。
- 成本统计报告脚本。
- Day 2 模块说明。
- 调用时序图。
- 30 秒面试话术。
- 21:00-23:00 三问复盘。

## 仍然刻意不做

- 不接真实 DeepSeek/Qwen API。
- 不引入 Redis。
- 不做真实分布式预算。
- 不写 ReAct 循环。
- 不做 RAG。
- 不做完整 PromptOps 或 Eval Gate 平台。

