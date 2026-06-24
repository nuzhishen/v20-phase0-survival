# V20 Phase 0 Survival

Phase 0 是 V20 计划的生存筛选周，用于验证核心能力、沉淀设计结论，并在 Day 6 完成全链路通关。它不是 P1 正式项目，也不承担平台化建设。

## 组织原则

- 一个 Phase 0 总仓库，Day 1 到 Day 6 各自独立。
- Mon-Fri 是能力模块，Day 6 是集成验收。
- 共享目录只保存稳定契约、测试工具和数据，不强行复用实验代码。
- P1 开始后重建正式的 `v20-tms-agent-runtime`，不直接复制本仓库的全部原型。

## 目录

```text
v20-phase0-survival/
├── shared/                    # 稳定契约与少量测试工具
├── data/                      # TMS、OTT、养老数据
├── day01_schema_fastapi/      # FastAPI + Pydantic 输入契约
├── day02_llm_budget/          # LLM Provider、预算、Retry、合规
├── day03_react_loop/          # 手写 ReAct 核心决策循环
├── day04_rag_pipeline/        # 最小 RAG Pipeline
├── day05_hybrid_rerank/       # 混合检索与 Reranker 对比
├── day06_pass_test/           # 全链路通关测试
├── docs/                      # Phase 0 决策、日志与复盘
└── scripts/                   # 跨日验证脚本
```

## 每日能力点

| Day | 目标 | 边界 |
|---|---|---|
| Day 1 | FastAPI、Pydantic v2、严格输入校验 | 不接 LLM、RAG 或 Agent |
| Day 2 | LLM 调用契约、Token 预算、Retry、Prompt 合规 | 5 次 Mock；真实小额调用可选 |
| Day 3 | 手写 ReAct 决策循环 | 核心循环不依赖 Agent 框架 |
| Day 4 | 切片、Embedding、Upsert、Search、Top-K | 不做复杂 RAG 平台或 GraphRAG |
| Day 5 | Dense + Sparse + Reranker 对比 | 基于 Day 4 结果做可量化实验 |
| Day 6 | RAG -> ReAct -> Tool -> DiagnosisResult | 固定输入、结构化输出、证据、HITL |

## 当前迁移状态

- Day 1 源码、测试、文档、规则和仓库外层学习资料已迁入。
- Day 2 源码、测试、Prompt、报告、文档和 IDE 配置已迁入。
- Day 3 到 Day 6 已创建可继续开发的目录骨架。
- 源目录 `C:\ai\day-001` 和 `C:\ai\day-002` 保持不变。

## 换账号接续

如果切换 Codex 登录账号，不依赖左侧历史会话或账号记忆接续项目。新的账号应从以下项目内文件恢复上下文：

- `AGENTS.md`：Phase 0 的强约束、每日边界和工程规则。
- `docs\account_switch_handoff.md`：账号切换后的接续入口、GitHub 仓库、验证命令和禁止复制项。
- `docs\migration_manifest.md`：Day 1、Day 2 的来源、提交和迁移范围。
- `day02_llm_budget\docs\day02_handoff_summary.md`：Day 2 给后续开发的交接总结。

当前主仓库已经托管在 GitHub：

```text
https://github.com/nuzhishen/v20-phase0-survival
```

换账号后优先从 GitHub clone 或打开本地 `C:\ai\codex\v20-phase0-survival`，再读取上述文档继续开发。

## 环境

建议在仓库根目录使用一个虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Day 1 和 Day 2 都使用顶层包名 `app`，因此测试必须在各自目录的独立进程中运行：

```powershell
.\scripts\run_phase0_tests.ps1
```

也可以单独运行：

```powershell
Push-Location .\day01_schema_fastapi
..\.venv\Scripts\python.exe -m pytest -q
Pop-Location

Push-Location .\day02_llm_budget
..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

## 严格范围

- Phase 0 不实现 WebSocket；后续需要流式输出时统一使用 SSE。
- 不提前引入 LangGraph、MCP、Redis、完整 Harness、复杂前端或管理平台。
- Day 3 的 ReAct 决策循环必须能脱离框架解释。
- Day 4 只跑通最小 RAG 链路。
- Harness 核心策略必须由工程师设计并能解释权衡。
