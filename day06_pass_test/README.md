# Day 06: Phase 0 Pass Test

## 固定输入

```text
设备 TMS-GD-001 报 OTA_TIMEOUT，
近 7 天失败率 0.18，
当前离线，
区域华南。
```

## 固定链路

```text
输入校验
-> RAG 检索 OTA 运维手册
-> ReAct 查询设备状态
-> 风险评估
-> HITL 判断
-> 结构化 DiagnosisResult
```

## 通过标准

1. 全链路不崩溃。
2. 返回结构化 `DiagnosisResult`。
3. 输出包含证据来源。
4. 离线和高风险操作触发 HITL。
5. 工具调用只使用 Mock，不执行真实 OTA、脚本或重启。
6. 能解释每一步为何做出该决策。

## 淘汰标准

无法完成 ReAct 核心循环，或无法解释决策与安全边界时，Phase 0 不通过。

