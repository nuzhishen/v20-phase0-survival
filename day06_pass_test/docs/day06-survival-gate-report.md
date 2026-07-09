# Day 6 Survival Gate Report

生成时间：2026-07-09  
运行入口：`python -m app.demo.survival_gate`  
测试入口：`pytest -q tests/test_survival_gate.py`  
通关结论：通过 Phase 0 Day6 标准，可进入 Phase 1。

## 1. 通关链路

```text
DeviceIssueQuery
-> RAG 检索 Day4 TMS 手册
-> Day5 风格 Hybrid alpha=0.6 + MockReranker
-> Day3 风格 ReAct 状态机
-> Mock Tool Calling
-> DiagnosisResult
-> GateMetrics
```

Day6 没有接真实 LLM、真实 OTA、脚本或重启。所有工具均为 Mock，失败也会转成 Observation。

## 2. 验证命令

```powershell
cd C:\ai\codex\v20-phase0-survival\day06_pass_test
..\.venv\Scripts\python.exe -m app.demo.survival_gate
..\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
Day6 pytest: 9 passed in 0.14s
Demo: total_cases=10, passed_cases=10
```

全仓回归：

```powershell
cd C:\ai\codex\v20-phase0-survival
.\scripts\run_phase0_tests.ps1
```

结果：

```text
Day1: 25 passed, 1 warning
Day2: 31 passed
Day3: 14 passed
Day4: 13 passed
Day5: 10 passed
Day6: 9 passed
```

Day1 的 warning 是既有 `StarletteDeprecationWarning`，不是本次 Day6 引入。

## 3. 指标表

| 指标 | 通关线 | 实测 | 结论 |
|---|---:|---:|---|
| End-to-End Success Rate | >= 80% | 100.00% | 通过 |
| No Crash Rate | 100% | 100.00% | 通过 |
| RAG Hit Rate@3 | >= 70% | 100.00% | 通过 |
| Tool Call Accuracy | >= 80% | 100.00% | 通过 |
| HITL Trigger Accuracy | >= 90% | 100.00% | 通过 |
| Fallback Correctness | >= 80% | 100.00% | 通过 |
| Explanation Completeness | 100% | 100.00% | 通过 |

说明：样本量 N=10，每条样例约等于 10 个百分点。Day6 指标用于通关裁定，不等同于生产统计显著性。检索质量的更稳定基线仍以 Day4/Day5 的 30 条评估集为准。

## 4. 10 条样例结果

| 样例 | 输入主题 | 状态 | RAG 引用 | HITL | 降级/拒绝 |
|---|---|---|---|---|---|
| case_01 | OTA_TIMEOUT Android 11 灰度重试 | ok | `tms_e1002,tms_e1007,tms_e1009` | 否 | - |
| case_02 | DEVICE_OFFLINE 不直接 OTA | ok | `tms_e1001,tms_e1007,tms_e1004` | 是 | `DEVICE_OFFLINE_REQUIRE_MANUAL_CHECK` |
| case_03 | FIRMWARE_MISMATCH 阻止升级 | ok | `tms_e1003,tms_e1004,tms_e1005` | 是 | - |
| case_04 | HIGH_FAILURE_RATE 华南先试点 | ok | `tms_e1004,tms_e1002,tms_e1003` | 是 | - |
| case_05 | SCRIPT_EXEC_ERROR 沙箱复现 | ok | `tms_e1005,tms_e1004,tms_e1001` | 是 | - |
| case_06 | UNKNOWN_CODE 不胡编 | degraded | `tms_e1008,tms_e1003,tms_e1002` | 是 | `UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK` |
| case_07 | OTA_TIMEOUT RAG 无结果降级 | degraded | `tms_e1002` | 否 | `FORCED_RAG_EMPTY`, L4 |
| case_08 | 设备工具异常转 Observation | degraded | `tms_e1002,tms_e1007,tms_e1009` | 是 | `query_device_status_TOOL_ERROR` |
| case_09 | batch_size=500 必须 HITL | ok | `tms_e1002,tms_e1007,tms_e1009` | 是 | - |
| case_10 | 直播卡顿误入 TMS 拒绝 | rejected | - | 否 | `CROSS_DOMAIN_QUERY` |

## 5. 失败和降级样例

| 场景 | 结果 | 价值 |
|---|---|---|
| 未知异常码 | 返回 degraded，不编造根因，触发 HITL | 证明系统知道自己不知道。 |
| RAG 无结果 | 降级到 L4 规则知识库，仍输出结构化建议 | 证明检索不是单点依赖。 |
| 工具异常 | 工具错误转 Observation，返回 degraded | 证明工具失败不会导致进程崩溃。 |
| 跨域输入 | 返回 rejected，不进入 TMS 工具链 | 证明领域边界可控。 |
| batch_size=500 | 风险 HIGH，HITL=true | 证明批量操作 blast radius 受控。 |

## 6. 通关裁定

裁定：通过。

理由：

- 10 条样例全部产生结构化结果。
- No Crash Rate = 100.00%。
- RAG、Tool、HITL、Fallback、Explanation 指标全部达到通关线。
- 失败样例没有隐藏，均以 `status`、`fallback_path`、`fallback_reason` 显式暴露。

## 7. 30 秒面试话术

我在 Phase 0 最后一日完成了一个最小 TMS 智能运维 Agent 闭环。用户输入设备异常问题后，系统先用 RAG 检索运维手册，再进入 ReAct 状态机决策，必要时调用模拟设备工具查在线状态、固件版本和 OTA 历史，最后生成结构化处理建议。

这不是 Prompt Demo，而是最小 Agent Runtime：含检索、状态机、工具调用、风险判断、HITL 标记和失败降级。我用 10 条通关样例验证，端到端成功率 100.00%，无崩溃率 100.00%，工具调用准确率 100.00%，HITL 触发准确率 100.00%。

这个结果说明我具备进入下一阶段 Context Engine 和生产级 Harness 训练的基础，但它只证明单机规则版闭环，不证明生产并发、队列、幂等、熔断和长期成本治理，这些会进入 P1 后续版本。

