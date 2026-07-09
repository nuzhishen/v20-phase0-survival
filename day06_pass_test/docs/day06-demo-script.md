# Day 6 Demo Script

用途：5 分钟通关演示脚本。  
入口：`day06_pass_test/`

## 1. 开场 30 秒

今天演示的是 Phase 0 Day6 通关测试，不是继续开发新功能。目标是把 Day3 手写 ReAct、Day4 RAG 语料和 Day5 Hybrid/Reranker 策略串成一个最小 Agent Runtime。

这条链路只做 TMS 智能运维场景，不接真实 LLM、不接真实 OTA、不做 LangGraph、MCP、Redis、前端或平台化服务。

## 2. 展示文件结构 30 秒

```text
day06_pass_test/
  app/agent/tms_agent.py
  app/agent/fallback_policy.py
  app/agent/diagnosis_pipeline.py
  app/tools/device_tools.py
  app/demo/survival_gate.py
  tests/test_survival_gate.py
```

说明：

- `tms_agent.py` 是状态机和结果契约。
- `fallback_policy.py` 是 RAG 证据和 L1-L4 降级。
- `diagnosis_pipeline.py` 是 10 条样例和指标计算。
- `device_tools.py` 是 Mock 工具，不碰真实设备。

## 3. 运行 Demo 60 秒

```powershell
cd C:\ai\codex\v20-phase0-survival\day06_pass_test
..\.venv\Scripts\python.exe -m app.demo.survival_gate
```

讲解输出重点：

- `total_cases=10`
- `passed_cases=10`
- End-to-End Success Rate = 100.00%
- No Crash Rate = 100.00%
- Tool Call Accuracy = 100.00%
- HITL Trigger Accuracy = 100.00%

强调：N=10 是通关样例，不是生产统计显著性。

## 4. 讲 3 条关键样例 120 秒

### OTA_TIMEOUT

链路：

```text
RAG 命中 tms_e1002
-> query_device_status
-> query_ota_history
-> estimate_batch_risk
-> should_require_hitl
-> DiagnosisResult
```

讲法：这是正常闭环，建议灰度重试，不直接全量。

### RAG 无结果

链路：

```text
force_rag_empty=True
-> fallback_path=L4
-> 规则知识库 tms_e1002
-> 仍返回结构化建议
```

讲法：检索失败不是系统失败，必须显式降级。

### 工具异常

链路：

```text
query_device_status 抛错
-> ToolResult(ok=false)
-> Observation
-> degraded DiagnosisResult
```

讲法：工具异常是业务状态，不应该让 Agent 进程崩溃。

## 5. 跑测试 60 秒

```powershell
cd C:\ai\codex\v20-phase0-survival\day06_pass_test
..\.venv\Scripts\python.exe -m pytest -q
```

预期：

```text
9 passed
```

再跑全仓：

```powershell
cd C:\ai\codex\v20-phase0-survival
.\scripts\run_phase0_tests.ps1
```

说明 Day1-Day6 都独立通过。

## 6. 收尾 30 秒

这次通关证明的是：我能把检索、状态机、工具调用、风险判断、HITL 和失败降级串成一个可运行、可测试、可解释的最小 Agent Runtime。

它不证明生产并发、队列、幂等、熔断和真实 LLM 成本治理。那些是 P1 正式项目要继续做的 Harness 能力。

