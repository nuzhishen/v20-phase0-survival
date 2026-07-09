# Phase 0 Day 6 — Survival Gate 通关规划(上午 09:30–11:00 执行方案)

> 定位:今天是**通关日**,不是开发日。上午把设计锁死、失败面想透、面试面练熟,给下午一个不跑偏的靶子。
> 本文件对应训练令"上午必须产出",配套 `day06-architecture.md`(Mermaid 全链路 + 数据契约)。
> 红线:11:00 前不碰业务代码;不加新功能;不调 RAG;不做 GraphRAG / Query Rewrite / 真实 LLM。

---

## 0. 一句话技术判断(背下来)

> Phase 0 通关不是证明我会调模型,而是证明我能把 **ReAct 状态机、RAG 检索层、工具调用层**串成一个**可运行、可测试、可解释**的最小 Agent Runtime。今天不再加功能,只验证**全链路闭环、失败兜底、通关裁定**。

---

## 1. 全链路流程(Query → RAG → ReAct → Tool → DiagnosisResult)

**主线一句话**:用户报设备异常 → RAG 查运维手册(失败降级)→ TopK 作 Observation 喂进 ReAct → 状态机决策调设备工具取证 → 生成结构化 `DiagnosisResult`(含风险等级与 HITL 标记)。

| 段 | 模块 | 职责 | 失败兜底 |
|---|---|---|---|
| ① 入口 | `app/demo/survival_gate.py` | 接收异常输入,跑 10 条样例,出通关裁定 | 单条失败不影响其余样例 |
| ② RAG | `retrieve_tms_context()` | 查 TMS 知识,L1→L4 降级,低分兜底 | Hybrid→Dense→硬编码;score<0.5 转人工 |
| ③ ReAct | `app/agent/tms_agent.py` | 规则版状态机决策,6 护栏 | max_steps / 白名单 / 重复终止 / 未知码兜底 |
| ④ Tool | `app/tools/device_tools.py` | 白名单工具取证 | 工具异常 → ToolResult(ok=false) 转 Observation |
| ⑤ 结果 | `DiagnosisResult` | 根因/证据/引用/观察/风险/HITL/建议 | 信息不足 → fallback_reason 转人工 |

> 详细流程图见 `day06-architecture.md` §1;状态机见 §2;降级阶梯见 §3;数据契约见 §4。

---

## 2. Day1–Day5 依赖审查清单(承 08:00–08:40 第一版)

| 天数 | 产物 | Day6 用途 | 是否必接 |
|---|---|---|---|
| Day1 | Pydantic Schema / FastAPI 骨架 | 输入校验参考 | 可选,**不拉进主链路** |
| Day2 | LLM Client / Token 计费 | 面试解释成本控制 | 可选,**不接真实 LLM** |
| Day3 | ReAct 规则状态机(§3.2–3.3) | 通关核心决策层 | **必接** |
| Day4 | RAG Retriever / score_threshold / domain 过滤 | 知识检索层 | **必接** |
| Day5 | Best Hybrid + Reranker + 降级链 | 最佳检索配置 | **必接,失败可降级** |
| Day6 | Survival Gate | 全链路入口与裁定 | **必做** |

> 红线:不要为了"完整集成"把 Day1 FastAPI、Day2 真实 LLM、Token Budget 全拉进主链路。Day6 主目标是 **ReAct + RAG + Tool 闭环**。
> 实况说明:Day2–5 产物目前是**设计笔记**(无可运行代码),Day6 是**按笔记设计新写一遍**,不是 import 老模块 —— 接口不一致时由适配层解决,不重构笔记里的设计。

---

## 3. 通关指标(数值下午实测填)

| 指标 | 计算方式 | 通关线 | 实测 |
|---|---|---|---|
| End-to-End Success Rate | 完整输出 DiagnosisResult / 总样例 | ≥80% | ___% |
| No Crash Rate | 无崩溃样例 / 总样例 | 100% | ___% |
| RAG Hit Rate@3 | 命中预期 section / 总样例 | ≥70% | ___% |
| Tool Call Accuracy | 工具选择正确 / 总样例 | ≥80% | ___% |
| HITL Trigger Accuracy | 高风险正确触发 HITL / 应触发样例 | ≥90% | ___% |
| Fallback Correctness | 失败时安全降级 / 失败样例 | ≥80% | ___% |
| Explanation Completeness | 能解释每一步 | 100% | ___% |

---

## 4. 失败场景清单(09:30–10:20 产出)

| # | 失败场景 | 处理策略 | 对应护栏/机制 |
|---|---|---|---|
| 1 | 未知异常码 | 不胡编,`fallback_reason=UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK`,转人工 | 未知码兜底 |
| 2 | RAG 无结果 / 低置信 | `low_confidence=true`,降级硬编码知识库,不塞错上下文 | score_threshold + L4 |
| 3 | 工具异常 | 转 `ToolResult(ok=false)` → Observation,不崩溃 | 工具异常转 Observation |
| 4 | 设备离线 | 查到 offline → 不建议直接 OTA,给离线处理建议 | 工具取证 + 规则决策 |
| 5 | 高风险 OTA / batch_size>100 | 只生成建议,`require_hitl=true`,不直接执行 | 高风险 HITL |
| 6 | Hybrid / Reranker 不可用 | L1→L2→L3→L4 逐级降级 | RAG 降级阶梯 |
| 7 | ReAct 死循环 | max_steps=6 + 重复 Action 2 次终止 | 双保险 |
| 8 | 跨域污染(直播卡顿误入 TMS) | domain=tms 过滤,拒绝/路由到 OTT | Payload 过滤(day-004 §5) |

---

## 5. 降级策略(一张表锁死)

| 组件失效 | 降级到 | 判定 |
|---|---|---|
| Reranker 不可用 | Hybrid 无 Reranker(→ 再退 MockReranker) | L1→L2 |
| Hybrid 不可用 | Dense Only | L2→L3 |
| RAG 整体 / Qdrant 挂 | InMemory / Day3 硬编码知识库 | L3→L4 |
| TopK 全 score<0.5 | low_confidence 转人工兜底 | 任意层之后 |
| 工具抛错 | ToolResult(ok=false) → Observation | 不崩溃 |
| ReAct 不稳 | 规则版状态机(本就不接真实 LLM) | 保持规则闭环 |

---

## 6. 面试攻击点表(整合训练令 7 问 + 三份笔记)

| # | 追问 | 脱稿答题方向 |
|---|---|---|
| 1 | 为什么这不是 Prompt Demo? | 它是最小 Agent Runtime:检索 + 状态机 + 工具调用 + 风险判断 + HITL + 失败降级,每步可断言、可测、可审计。 |
| 2 | 为什么 Day6 不继续调 RAG? | 今天是通关不是优化检索;一次只验证一件事——全链路闭环,不动检索算法避免污染裁定。 |
| 3 | 为什么要串 Day3/4/5? | ReAct、RAG、Tool 各自跑通 ≠ Agent 闭环;Agent 的能力是**链路可靠性**,不是单点。 |
| 4 | RAG 检索错了怎么办? | score<0.5 判低置信,降级/转人工,**不强塞错误上下文**;检索的锅(Recall 低)和决策的锅分开归因(day-004 §6.4)。 |
| 5 | 工具调用失败怎么办? | 转 Observation,不让 Agent 崩;今天不做自动重试(那是后续),失败先变可见可测(day-003 攻击点 #7)。 |
| 6 | 高风险操作怎么办? | 只生成建议,`risk=HIGH` 或 `batch_size>100` 强制 HITL,状态机里的强制转移,模型跳不过。 |
| 7 | 为什么不用 LangGraph? | 先掌握原语(状态/转移/终止/白名单/HITL)再上框架;面试考设计权衡不是 API;要可控可测可审计的底座(day-003 §4)。 |
| 8 | AI 生成代码可以吗? | 可以,但核心循环(6 护栏)手写;每一步我能解释,讲不清就不算通过(Kimi 红线)。 |
| 9 | 如何判断 Phase 0 通过? | 看全链路稳定性、可解释性、真实指标、失败复盘 —— 10 条样例 ≥8 通过且 No Crash=100%。 |

### 30 秒面试话术(报告末尾用,含真实数字)
> 我在 Phase 0 最后一日完成了一个最小 TMS 智能运维 Agent 闭环。用户输入设备异常问题后,系统先用 RAG 检索运维手册,再进入 ReAct 状态机决策,必要时调用模拟设备工具查在线状态、固件版本和 OTA 历史,最后生成结构化处理建议。这不是 Prompt Demo,而是最小 Agent Runtime:含检索、状态机、工具调用、风险判断、HITL 标记和失败降级。我用 10 条通关样例验证,端到端成功率 ___%、无崩溃率 ___%、工具调用准确率 ___%、HITL 触发准确率 ___%。这说明我具备进入下一阶段 Context Engine 与生产级 Harness 训练的基础。

---

## 7. 锁定执行范围(10:20–11:00 产出,不再加需求)

### 7.1 统一文件结构(路径锁死,禁止 ChatGPT/DeepSeek/Qwen 路径打架)
```
app/
  agent/  __init__.py  tms_agent.py  diagnosis_pipeline.py  fallback_policy.py
  demo/   __init__.py  survival_gate.py
  tools/  device_tools.py
tests/    test_survival_gate.py
docs/     day06-survival-gate-plan.md  day06-architecture.md
          day06-survival-gate-report.md  day06-elimination-review.md  day06-demo-script.md
```
统一入口:`python -m app.demo.survival_gate` / `pytest -q tests/test_survival_gate.py`
禁用旧命名:`app/gate_agent.py` / `tests/test_gate.py` / `docs/gate_report.md` / `docs/phase0_pass_report.md`

### 7.2 今日禁止清单
- ❌ 加新功能  ❌ 调 RAG 检索算法  ❌ GraphRAG  ❌ Query Rewrite
- ❌ LangGraph 深集成  ❌ MCP/SSE/P3/前端  ❌ 接真实 LLM  ❌ Token Budget 拉进主链路

### 7.3 下午固定执行顺序(锁定,便于收口)
| 时间 | 任务 |
|---|---|
| 14:00–14:45 | 接入 Day5 最佳 Retriever(能返回 TopK / 可降级) |
| 14:45–15:30 | 接入 Day3 ReAct 状态机(保留 6 护栏) |
| 15:30–16:15 | 接入模拟 Tool Calling(结果转 Observation) |
| 16:15–17:00 | 跑 10 条通关样例,记录成功/失败 |
| 17:00–17:40 | 只修主链路崩溃点,不加新功能 |
| 17:40–18:00 | 生成报告初稿(指标真实,不留空表) |

### 7.4 10 条通关样例(下午验收靶子)
| # | 输入 | 期望 |
|---|---|---|
| 1 | OTA_TIMEOUT + Android 11 | 检索 OTA 知识,建议灰度重试 |
| 2 | DEVICE_OFFLINE | 查状态,不建议直接 OTA |
| 3 | FIRMWARE_MISMATCH | 阻止升级,HITL |
| 4 | HIGH_FAILURE_RATE + 华南 | 风险高,先试点 |
| 5 | SCRIPT_EXEC_ERROR | 建议沙箱复现,不直接重试 |
| 6 | UNKNOWN_CODE | 不胡编,人工排查 |
| 7 | OTA_TIMEOUT + RAG 无结果 | 降级硬编码知识库 |
| 8 | 设备工具异常 | 转 Observation,不崩溃 |
| 9 | batch_size=500 | 必须 HITL |
| 10 | 直播卡顿误入 TMS | 拒绝/路由到 OTT,不污染 TMS(只做路由检查) |

---

## 8. 通关裁定标准(晚间用)

| 裁定 | 标准 | 动作 |
|---|---|---|
| 通过 | 10 条 ≥8 通过;No Crash=100%;能解释每一步 | 周日休息,周一进 Phase 1 |
| 有条件通过 | 5–7 条通过;核心 TMS 场景通过;失败可定位 | 周日休息,周一补 Day3/4/5 薄弱环节 |
| 不通过 | Demo 跑不了;核心场景失败;讲不清链路 | 触发熔断,重评估或重做 Phase 0 |

> 最低合格线:5 条核心 TMS 样例跑通 + No Crash=100% + 报告真实。
> 优秀线:10/10 通过 + RAG/Tool/HITL 指标达标 + 面试话术脱稿。

---

## 9. 上午验收自检(对照训练令"上午必须产出")
- [x] 全链路流程 → §1 + architecture §1
- [x] 依赖关系 → §2
- [x] 通关指标 → §3
- [x] 失败场景 → §4
- [x] 降级策略 → §5
- [x] 面试解释(为什么是最小 Agent Runtime 而非 Prompt Demo)→ §6 #1
- [x] Mermaid 全链路 + 状态机 + 降级阶梯 + 数据契约 → `day06-architecture.md`
- [x] 锁定执行范围 + 禁止清单 → §7
