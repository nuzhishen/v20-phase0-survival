# Day 03 阻塞记录

## 1. 哪个场景没跑通？

当前 10 条 TMS 样例和最低 5 条测试均设计为可跑通场景。主要风险不是功能不可运行，而是规则版 Action 选择逻辑仍然依赖硬编码知识库，覆盖面有限。

## 2. 哪个 Action 选择逻辑不稳定？

最不稳定的是 `estimate_operation_risk` 的阈值：

- `failure_rate_7d >= 0.10` 当前直接判 HIGH。
- `batch_size > 100` 当前直接判 HIGH。
- 设备离线会改写推荐动作，但不单独作为风险工具输入。

这些规则适合 Day 3 训练，但进入 Day 4 / Day 6 前需要用更多样例校准。

## 3. 哪些代码是 Codex 辅助骨架？

Codex 生成了以下文件骨架和测试骨架：

- `app/react_types.py`
- `app/knowledge_base.py`
- `app/tools.py`
- `tests/test_react_loop.py`
- `docs/react_accuracy_report.md`
- `docs/day03-what-blocked.md`

## 4. 哪些核心逻辑是我手写？

本轮由 Codex 根据你的 Day 3 训练令直接实现了核心逻辑，但实现方式是手写规则状态机，不是框架生成循环：

- `run_react_loop()` 状态流转。
- Action 选择顺序。
- `max_steps=6` 安全终止。
- 工具白名单。
- 工具异常转 Observation。
- 未知异常码不胡编。
- HIGH / 批量操作触发 HITL。
- 设备离线时暂缓远程 OTA。

## 5. 明天 RAG 前最大的风险是什么？

最大风险是把 `lookup_error_knowledge()` 从硬编码知识库替换为检索接口后，Observation 质量会变得不稳定。

Day 4 前必须注意：

- 检索结果为空时不能胡编。
- Top-K 证据必须带来源。
- ReAct 不应因为低质量检索结果直接执行高风险动作。
- Day 3 的未知异常码兜底要保留。

## 6. 今天是否出现死循环或 Token 膨胀风险？

今天没有接真实 LLM，因此没有 Token 膨胀。死循环风险通过两层控制：

- `max_steps=6`。
- 同一 Action 连续重复 2 次立即终止。

未来接真实 LLM 后，仍需要限制 Thought 长度、历史轮数和工具 Schema 数量，否则会重新引入 Day 2 记录过的 Token 膨胀风险。

## 三问复盘

### 今天做出来什么？

完成规则版 ReAct 状态机、ToolRegistry、工具异常 Observation、未知异常码兜底、HITL 判断、10 条 TMS 样例评估、准确率报告和阻塞记录。

### 今天学到了什么？

ReAct 不是 Prompt，而是状态机。生产级 Agent 不能只依赖模型自由发挥，必须显式控制状态、工具、Observation、终止条件和安全边界。

### 今天什么没做出来？

没有接真实 LLM、没有接 RAG、没有做复杂 Prompt Parser、没有实现 Checkpoint / Retry / Circuit Breaker / DLQ。这些是刻意收敛，避免 Day 3 变成平台化开发。
