# Phase 0 W1 Handoff To Phase 1 P2 Context Engine

交接日期：2026-07-10  
当前仓库：`C:\ai\codex\v20-phase0-survival`  
当前阶段：Phase 0 生存筛选周已完成，下一阶段进入 Phase 1 / P2 OTT + 养老 Context Engine。  
核心裁定：Phase 0 通过；可以进入 Phase 1，但 P2 必须保持 Context Engine 底座范围，禁止扩张成业务系统。

## 1. 结论先行

Phase 0 已完成 Day1-Day6 的最小能力链路验证：

```text
输入契约
-> LLM 调用契约与预算意识
-> 手写 ReAct 状态机
-> 最小 RAG Pipeline
-> Hybrid Retrieval + MockReranker
-> ReAct + RAG + Tool Calling Survival Gate
```

Day6 通关结果：

```text
Demo: total_cases=10, passed_cases=10
Day6 pytest: 9 passed
Phase0 full regression:
  Day1 25 passed, 1 warning
  Day2 31 passed
  Day3 14 passed
  Day4 13 passed
  Day5 10 passed
  Day6 9 passed
```

Day1 的 warning 是既有 `StarletteDeprecationWarning`，不影响 Phase 0 裁定。

## 2. 仓库当前边界

| 项 | 结论 |
|---|---|
| 仓库性质 | V20 Phase 0 survival-week 原型仓库。 |
| 是否是 P1/P2 正式项目 | 否。后续正式项目应重建，不直接把本仓库当生产代码。 |
| Day1-Day6 关系 | 每天独立可运行，Day6 只负责跨日集成通关。 |
| 顶层 `app` 包风险 | Day1-Day6 多个目录都有独立 `app` 包，测试必须分目录运行。 |
| 后续流式输出 | 不用 WebSocket，统一 SSE。 |
| Phase 0 禁止倒灌 | 不把 P2/P3、前端、平台化、LangGraph、MCP、Redis 等内容倒灌回 Phase 0。 |

## 3. Day1-Day6 交接清单

### Day1: Schema + FastAPI 输入契约

| 项 | 内容 |
|---|---|
| 目录 | `day01_schema_fastapi/` |
| 核心能力 | Pydantic v2 严格输入校验、FastAPI 薄路由、未知字段拒绝、危险隐式转换拒绝。 |
| 后续价值 | P2 可复用“输入契约必须显式”的工程习惯，但不要把 Day1 FastAPI 直接搬进 P2。 |
| 验证 | `25 passed, 1 warning` |
| 注意 | warning 是既有 Starlette/httpx deprecation，不是 P2 阻塞。 |

### Day2: LLM Provider + Token Budget + Retry

| 项 | 内容 |
|---|---|
| 目录 | `day02_llm_budget/` |
| 核心能力 | Provider 契约、Mock LLM、Token 预算、Retry 分类、Prompt 合规。 |
| 后续价值 | P2 接 Spring AI / Python RAG 服务时，要延续 provider contract 和 budget 思维。 |
| 验证 | `31 passed` |
| 注意 | P2 初期不接复杂成本平台，只保留可解释的调用契约和预算意识。 |

### Day3: 手写 ReAct 状态机

| 项 | 内容 |
|---|---|
| 目录 | `day03_react_loop/` |
| 核心能力 | `Thought -> Action -> Observation -> Final` 规则版状态机。 |
| 已有护栏 | `max_steps=6`、工具白名单、未知码兜底、工具异常转 Observation、HIGH/batch HITL、离线设备暂缓 OTA。 |
| 后续价值 | P2 不是 Agent 主项目，但多轮 Context 使用工具时仍要保留“证据不能绕过安全判断”的思想。 |
| 验证 | `14 passed` |
| 注意 | 不要在 P2 深挖 LangGraph；P2 只需要 Context Engine 底座。 |

### Day4: 最小 RAG Pipeline

| 项 | 内容 |
|---|---|
| 目录 | `day04_rag_pipeline/` |
| 核心能力 | `chunk -> embed -> upsert -> search -> top_k`。 |
| 数据 | TMS 运维手册、OTT FAQ、养老健康指南；30 条 eval query。 |
| 指标 | Recall@5 `100.00%`，Context Precision@5 `94.00%`，平均检索延迟约 `0.49 ms`。 |
| 后续价值 | P2 的 Context Engine 可从 Day4 的数据装载、eval query、fallback 思路起步。 |
| 注意 | Day4 baseline 不要被 Day5/Day6/P2 覆盖。 |

### Day5: Hybrid Retrieval + MockReranker

| 项 | 内容 |
|---|---|
| 目录 | `day05_hybrid_rerank/` |
| 核心能力 | Dense、Sparse/BM25、Weighted/RRF Fusion、MockReranker、FallbackReranker。 |
| 最终配置 | `Best Hybrid + MockReranker (Hybrid alpha=0.6)` |
| 指标 | Dense Recall@3 `90.00%`，Final Recall@3 `100.00%`，MRR `1.0000`。 |
| 后续价值 | P2 Context Engine 的第一版检索策略可参考 Day5：Dense 负责语义，Sparse 负责错误码/版本号/精确 token，Reranker 只做候选重排。 |
| 注意 | P2 不做 GraphRAG 深挖，不做 Query Rewrite 大工程，不把 Reranker 当成系统可用性的单点依赖。 |

### Day6: Survival Gate 全链路通关

| 项 | 内容 |
|---|---|
| 目录 | `day06_pass_test/` |
| 核心链路 | `DeviceIssueQuery -> RAG -> ReAct -> Tool -> DiagnosisResult -> GateMetrics` |
| 关键文件 | `app/agent/tms_agent.py`、`app/agent/fallback_policy.py`、`app/agent/diagnosis_pipeline.py`、`app/tools/device_tools.py`、`app/demo/survival_gate.py`、`tests/test_survival_gate.py` |
| 通关样例 | 10 条，覆盖 OTA_TIMEOUT、DEVICE_OFFLINE、FIRMWARE_MISMATCH、HIGH_FAILURE_RATE、SCRIPT_EXEC_ERROR、UNKNOWN_CODE、RAG 无结果、工具异常、大批量 HITL、OTT 跨域拒绝。 |
| 指标 | End-to-End、No Crash、RAG Hit@3、Tool Accuracy、HITL Accuracy、Fallback Correctness、Explanation Completeness 均为 `100.00%`。 |
| 后续价值 | P2 虽然不做 Agent 主项目，但必须继承“Context 只是证据，不是最终决策”的边界。 |
| 注意 | Day6 只证明单机规则版闭环，不证明生产并发、队列、幂等、熔断、DLQ、真实 LLM 成本治理。 |

## 4. 当前验证命令

全仓回归：

```powershell
cd C:\ai\codex\v20-phase0-survival
.\scripts\run_phase0_tests.ps1
```

单独验证 Day6：

```powershell
cd C:\ai\codex\v20-phase0-survival\day06_pass_test
..\.venv\Scripts\python.exe -m app.demo.survival_gate
..\.venv\Scripts\python.exe -m pytest -q
```

Day1-Day6 都有独立顶层 `app` 包时，不要在仓库根目录直接混跑 `pytest`。

## 5. Phase 1 P2 目标

P2 名称：OTT / 养老 Context Engine。  
周期：W2-W3。  
目标：只做 Context Engine 底座，证明 RAG、Context Engineering、Spring AI / Python RAG 服务集成能力。

P2 不是：

- OTT 运营分析平台。
- 养老推荐系统。
- 复杂业务后台。
- GraphRAG 平台。
- PromptOps 平台。
- 多 Agent 项目。

P2 是：

- 知识库装载、切片、检索、评估、上下文压缩和会话上下文的底座。
- 面向 OTT FAQ、养老健康档案、设备运维手册的统一 Context 查询能力。
- Java/Spring AI 调用 Python RAG 服务的异构集成样板。

## 6. P2 W2-W3 执行范围

### W2 建议范围

| 日程 | 主题 | 交付 |
|---|---|---|
| W2 Mon | Spring AI + Qdrant 集成 | Spring Boot + Spring AI 骨架，加载 OTT FAQ。 |
| W2 Tue | Java -> Python RAG 通信 | gRPC 或 REST 小实验，记录延迟，不超过半天扩张。 |
| W2 Wed | Prompt 注入与隐私防护 | 输入/输出安全网关，养老隐私攻击样例。 |
| W2 Thu | Redis Session / 记忆管理 | 多轮上下文合并策略，只做底座。 |
| W2 Fri | RAGAS / 自定义评估 | Faithfulness、Context Precision、Recall@K。 |
| W2 Sat | Docker Compose | Spring Boot、Python RAG、Qdrant、Redis 一键启动。 |

### W3 建议范围

| 日程 | 主题 | 交付 |
|---|---|---|
| W3 Mon | Multi-Query 查询重写 | 小实验即可，不做 Query Rewrite 平台。 |
| W3 Tue | 状态机理解 | 可画状态机，不做 LangGraph 深集成。 |
| W3 Wed | Tool Calling 只做查询工具 | `query_ott_status`、`query_elderly_record`、`query_device_log`。 |
| W3 Thu | SandboxExecutor 抽象 | E2B 优先、Docker 备选，只做接口和安全策略。 |
| W3 Fri | Trace / Observability | Trace ID 贯穿一次调用。 |
| W3 Sat | P2 v2.0 集成 | README、架构图、5 分钟演示。 |

## 7. P2 必须保留的红线

| 红线 | 说明 |
|---|---|
| 不做 GraphRAG 深挖 | 只保留概念级理解，不做图谱系统。 |
| 不做复杂养老推荐 | 养老只作为 Context 数据域，不做医疗推荐或业务闭环。 |
| 不做 OTT 运营分析平台 | OTT 只做 FAQ / 运维查询，不做报表和运营后台。 |
| 不做前端平台 | P2 以 API、README、Swagger 或简单脚本演示为主。 |
| 不做完整 Eval Gate 平台 | 只保留评估脚本和报告。 |
| 不做多 Agent 扩张 | 多 Agent 最多后续 W13 轻量演示，不属于 P2。 |
| 不覆盖 Phase 0 baseline | Day4/Day5 指标保留为历史基线。 |

## 8. P2 可复用的 Phase 0 设计结论

- 输入契约要显式，未知字段和危险隐式转换要拒绝。
- RAG 只提供证据，不直接替代业务判断。
- Dense 负责语义召回，Sparse/BM25 负责错误码、版本号、英文 token、数字和专业术语。
- Reranker 只能重排候选，不能解决第一阶段漏召回。
- 低置信和空结果要 fallback，不强塞错误上下文。
- 工具失败要转 Observation，不让链路崩溃。
- 指标必须由脚本或测试计算，不能手填。
- Demo 成功不等于生产可用，报告里要写清能力边界。

## 9. P2 项目启动建议

### 9.1 技术路线评估与最终决策

结合 V20 完整计划、Phase0 Day1-Day6 实际产物和 P2 的 W2-W3 训练目标，最终建议是：

```text
新启一个 P2 独立项目，采用 Java + Python 双模块。
不要继续在 Phase0 的 d1-d6 目录上扩写。
不要做纯 Python 项目。
不要做纯 Java 重写 RAG 项目。
```

判断依据：

| 方案 | 优点 | 问题 | 裁定 |
|---|---|---|---|
| 继续在 Phase0 / Day1-Day6 基础上扩写 | 启动最快，能复用已有 Python RAG 和 ReAct 原型 | 会污染 Phase0 生存筛选仓库；Day1-Day6 多个顶层 `app` 包已经是独立原型；P2 会倒灌进 P0，后续难以讲清边界 | 不采用 |
| 新启纯 Python 项目 | 复用 Day4/Day5/Day6 成本低；RAG/RAGAS/Hybrid/Reranker 生态顺手 | 无法体现 W2 明确要求的 Spring AI；削弱“Java 存量系统如何集成 AI”的差异化；面试容易被看成 Python RAG Demo | 不采用 |
| 新启纯 Java 项目 | 强化 Java 背景，符合 Spring AI 学习目标 | RAGAS、Hybrid/Reranker、快速实验和评估会低效；容易把两周时间耗在重写 Python 已验证能力上；不利于 W2-W3 交付稳定 Demo | 不采用 |
| 新启 Java + Python 双模块项目 | Java 负责 Spring AI 企业入口和网关；Python 负责 Context Runtime、RAG、Hybrid、Reranker、RAGAS、安全网关；能承接 Phase0 成果，也能强化 Java 差异化 | 需要控制模块边界，避免变成平台化项目 | 采用 |

最终架构判断：

```text
Java = 企业接入面 / Spring AI / Controller / Swagger / 调用 Python Context Runtime
Python = Context Engine 核心 / RAG / Hybrid / Reranker / RAGAS / Prompt 注入防御 / Session Context
Qdrant = 向量库
Redis = Session / 短期上下文
Docker Compose = 一键演示环境
```

这条路线最符合 V20 的主叙事：

```text
Java 负责企业级接入与治理，Python 负责 AI Runtime / Context Runtime。
```

P2 的面试卖点不是“我又做了一个 RAG Demo”，而是：

```text
我把 Java 存量系统接入 AI Context Engine：
Spring AI 负责企业入口，Python Runtime 负责检索、评估、安全和上下文处理。
两者通过 REST/gRPC 解耦，既保留 Java 工程优势，也利用 Python AI 生态效率。
```

### 9.2 为什么不能继续写在 Phase0 仓库里

Phase0 仓库的定位已经完成：

- Day1-Day6 是生存筛选周原型，不是 P2 正式工程。
- Day1-Day6 都有独立边界，且多个目录使用顶层 `app` 包，继续叠加 P2 会增加导入冲突和测试混乱。
- Phase0 的价值是保留可回溯基线：Day4 Dense、Day5 Hybrid、Day6 Survival Gate。
- P2 需要独立 README、Docker Compose、架构图和演示脚本，便于后续进入 P1/P3 时讲清三项目关系。

因此，P2 只复用 Phase0 的设计结论和少量数据/评估思路，不直接复制整个 Phase0 原型。

### 9.3 P2 推荐仓库结构

建议新建正式目录，不在 Phase 0 仓库里继续堆正式项目：

```text
C:\ai\codex\v20-p2-context-engine
```

建议第一批目录：

```text
v20-p2-context-engine/
  java-control-entry/       # Spring Boot / Spring AI 轻量入口
  python-context-runtime/   # FastAPI 或 gRPC RAG 服务
  data/
    ott/
    elderly/
    tms/
  eval/
  docs/
  docker-compose.yml
```

模块职责：

| 模块 | 语言 | 职责 | 明确不做 |
|---|---|---|---|
| `java-context-gateway` | Java / Spring Boot / Spring AI | 企业入口、Swagger、ChatClient/Advisor/RAG 调用样例、调用 Python Context Runtime、记录 REST vs gRPC 延迟 | 不做复杂后台、不做 Admin Dashboard、不做完整 P3 Control Plane |
| `python-context-runtime` | Python | RAG Pipeline、Hybrid Retrieval、Reranker、RAGAS、自定义评估、Prompt 注入防御、Redis Session Context | 不做完整 Agent Runtime、不做 LangGraph 深集成、不做 P1 Harness |
| `data/` | 文档数据 | OTT FAQ、养老健康档案/指南、TMS 运维手册 | 不引入真实敏感个人信息 |
| `eval/` | 评估资产 | OTT10 + 养老10 + 设备10 的评估集、攻击 Prompt、结果报告 | 不做 Eval Gate 平台 |
| `docs/` | 文档 | 架构图、W2/W3 日志、效果评估报告、面试话术 | 不写营销页 |

### 9.4 W2-W3 实际执行调整

原计划中 W3 写了 “LangGraph + 工具调用 + 安全”，但结合 P2 的“只做 Context Engine 底座”红线，应做如下收敛：

| 原计划项 | 调整后做法 | 原因 |
|---|---|---|
| LangGraph 核心、状态机、条件路由 | 只做最简状态机脚本和流程图，证明脱离框架也能解释；不深集成到 P2 主链路 | 防止 P2 变成 Agent 项目 |
| Tool Calling | 只做查询型工具：`query_ott_status`、`query_elderly_record`、`query_device_log` | P2 是 Context Engine，不做高危执行工具 |
| SandboxExecutor | 保留接口抽象和危险输入拦截演示，不做复杂沙箱平台 | P2 只需要证明安全意识，E2B/Docker 深化留给 P1 |
| Trace / LangSmith | 只做一次请求的 trace-id 贯穿：Java -> Python -> Retriever -> Response | 不做完整可观测平台 |
| Multi-Query | 小实验，记录命中率变化；不做 Query Rewrite 平台 | 防止检索优化失控 |

W2-W3 的最高优先级交付应是：

1. Java Spring AI 入口能调用 Python Context Runtime。
2. Python 能加载 OTT / 养老 / TMS 三类知识并返回带引用的上下文。
3. 评估脚本能输出 Faithfulness、Context Precision、Recall@K 或自定义替代指标。
4. Prompt 注入和隐私攻击样例有真实拦截率。
5. Docker Compose 能一键启动 Java、Python、Qdrant、Redis。
6. README 能讲清：这是 Context Engine，不是业务平台。

### 9.5 Phase0 到 P2 的复用边界

| Phase0 产物 | P2 复用方式 | 禁止事项 |
|---|---|---|
| Day1 Pydantic / FastAPI 输入契约 | 复用“严格输入契约”思想；Python Runtime 可参考 schema 风格 | 不直接搬 Day1 FastAPI 项目 |
| Day2 Provider / Token Budget | 复用 provider contract、预算意识和 retry 分类话术 | 不做预算平台 |
| Day3 ReAct 状态机 | 复用“证据不能绕过安全判断”和 tool observation 思想 | 不把 P2 做成 Agent 主项目 |
| Day4 RAG Pipeline | 复用数据加载、切片、eval set 和 fallback 思路 | 不覆盖 Day4 baseline |
| Day5 Hybrid/Reranker | 复用 Dense + Sparse + alpha + MockReranker 的实验路线 | 不把 Reranker 当单点依赖 |
| Day6 Survival Gate | 复用可解释输出、fallback_reason、trace、metrics 报告风格 | 不把 Day6 TMS Agent 原型搬成 P2 主链路 |

### 9.6 面试叙事

P2 的推荐 30 秒话术：

```text
P2 我没有扩成 OTT 或养老业务系统，而是严格做 Context Engine 底座。
Java 侧用 Spring Boot / Spring AI 做企业接入入口，提供 Controller、Swagger 和 ChatClient/Advisor 调用样例；
Python 侧负责真正的 Context Runtime，包括文档切片、Hybrid Retrieval、Reranker、RAGAS/自定义评估、Prompt 注入防御和 Redis Session Context。
两侧通过 REST/gRPC 解耦，Java 保留企业工程优势，Python 利用 AI 生态效率。
这个项目证明我能把 Java 存量系统和 AI 检索上下文能力结合起来，而不是只写一个 Python RAG Demo。
```

如果为了短期连续性继续放在本仓库，也必须新建独立目录并明确标注实验性质，不能污染 Day1-Day6 原型和测试基线。

## 10. 下一会话推荐读取顺序

1. `AGENTS.md`
2. `README.md`
3. `docs/phase0_w1_handoff_to_phase1_p2.md`
4. `docs/phase0_final_review.md`
5. `day06_pass_test/docs/day06-survival-gate-report.md`
6. `day05_hybrid_rerank/docs/hybrid_vs_dense_report.md`
7. `day04_rag_pipeline/docs/rag_baseline_report.md`
8. `day03_react_loop/docs/react_accuracy_report.md`

## 11. 最终裁定

Phase 0 W1 通过。  
下一步进入 Phase 1 / P2 Context Engine。  
执行时必须保持收敛：只做 Context Engine 底座，不扩张为复杂业务系统。
