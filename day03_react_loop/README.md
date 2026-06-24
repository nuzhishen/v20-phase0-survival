# Day 03: Manual ReAct Loop

## 目标

手写一个最小、可解释、可测试的 ReAct 决策循环，绑定 TMS 故障诊断场景：

```text
异常码 -> 判断下一步 -> 查询知识/设备状态 -> 观察结果 -> 建议操作
```

## 必须完成

- 明确的状态模型和最大步数。
- Thought/Action/Observation 的结构化内部状态。
- 工具白名单和参数校验。
- 重复状态或重复动作检测。
- Mock LLM 和 Mock Tool 测试。
- 决策准确率样例与失败复盘。

## 禁止

- 不依赖 LangGraph 或其他 Agent 框架实现核心循环。
- 不调用真实高风险工具。
- 不实现 Checkpoint、DLQ、分布式队列或完整 Harness。

## 文件结构

```text
app/
  react_types.py      # ReactState / ToolCall / ToolResult / DiagnosisResult
  knowledge_base.py   # 最小 TMS 异常码知识库
  tools.py            # Mock 工具函数和 ToolRegistry
  react_loop.py       # 手写规则版 ReAct 状态机
tests/
  test_react_loop.py
docs/
  transformer_kv_cache_react_notes.md
  react_accuracy_report.md
  day03-what-blocked.md
```

## 运行

从 Day 3 目录运行，避免和 Day 1 / Day 2 的顶层 `app` 包冲突：

```powershell
cd C:\ai\codex\v20-phase0-survival\day03_react_loop
..\.venv\Scripts\python.exe -m app.react_loop
..\.venv\Scripts\python.exe -m pytest -q
```

如果没有仓库根目录虚拟环境，可使用当前 Python：

```powershell
python -m app.react_loop
python -m pytest -q
```

## 当前实现边界

- Thought 由确定性规则选择，不接真实 LLM。
- Action 只能调用 `TOOL_REGISTRY` 白名单。
- Observation 记录工具成功、空结果或异常。
- Final 固定返回结构化 `DiagnosisResult`。
- `max_steps=6`，同一 Action 连续重复 2 次时安全终止。
- 工具异常转 Observation，不让 Agent 崩溃。
