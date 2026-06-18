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

