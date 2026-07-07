# Codex Account Switch Handoff

本文档用于在更换 Codex 登录账号后恢复 V20 Phase 0 Survival 项目上下文。它只记录可迁移的项目事实、工程边界和操作入口，不迁移认证、会话、令牌或账号级记忆文件。

## 接续原则

- 以 GitHub 仓库和项目内文档作为唯一可靠交接源。
- 不依赖 Codex App 左侧历史会话、当前账号记忆或本机临时缓存。
- 不复制 `C:\Users\15814\.codex\auth.json`、系统凭据、会话 JSONL、插件缓存或桌面 App 状态目录。
- 新账号第一次接手时，先读 `AGENTS.md`、本文件、`docs\migration_manifest.md`、`docs\day03_to_day04_handoff.md` 和 `docs\day05_to_day06_handoff.md`。

## 项目身份

| 项 | 值 |
|---|---|
| 项目名 | `v20-phase0-survival` |
| 阶段 | V20 Phase 0 生存筛选周 |
| 当前本地路径 | `C:\ai\codex\v20-phase0-survival` |
| 当前兼容入口 | `C:\ai\day-003`，目前是指向项目目录的 junction |
| GitHub | `https://github.com/nuzhishen/v20-phase0-survival` |
| 默认分支 | `main` |
| 最近已知 Day 5 提交 | `8ab34b79ada138dbdbade7c99e970ddd871477c5` |
| 提交说明 | `phase0-day5 hybrid retrieval reranker comparison` |

## 必读文件顺序

1. `AGENTS.md`
2. `README.md`
3. `docs\account_switch_handoff.md`
4. `docs\migration_manifest.md`
5. `docs\phase0_decision_record.md`
6. `day02_llm_budget\docs\day02_handoff_summary.md`
7. `docs\day03_to_day04_handoff.md`
8. `docs\day05_to_day06_handoff.md`
9. `day05_hybrid_rerank\docs\hybrid_vs_dense_report.md`
10. `day05_hybrid_rerank\docs\day05-what-blocked.md`
11. `day03_react_loop\docs\react_accuracy_report.md`
12. `day03_react_loop\docs\day03-what-blocked.md`
13. `docs\phase0_daily_log.md`
14. `docs\phase0_final_review.md`

## 项目边界

- Phase 0 是生存筛选周，不是 P1 正式生产项目。
- Day 1 到 Day 5 保持独立可运行，Day 6 负责跨日集成。
- 不引入 WebSocket；后续流式输出统一走 SSE。
- 不引入 LangGraph、MCP、Redis、前端、管理后台或平台化服务。
- 不实现 P2 Context Engine 或 P3 Control Plane。
- Day 3 必须手写 ReAct 决策循环，不能用框架生成核心循环。
- Day 4 只做 `chunk -> embed -> upsert -> search -> top_k`。
- Day 5 只在 Day 4 基础上比较 dense retrieval 与 hybrid retrieval plus reranking。

## 已迁移内容

Day 1：

- 来源：`C:\ai\day-001\tms-agent-phase0-day1`
- 迁移：16 个 Git 已跟踪文件。
- 补充：`C:\ai\day-001\docs` 下 5 份学习材料，已放入 `day01_schema_fastapi\docs\source_materials\`。

Day 2：

- 来源：`C:\ai\day-002`
- 迁移：54 个 Git 已跟踪文件。
- 重点交接：`day02_llm_budget\docs\day02_handoff_summary.md`。

Day 3 到 Day 6：

- Day 3 规则版最小 ReAct 状态机已完成。
- Day 4 最小 RAG Pipeline 已完成。
- Day 5 Hybrid Retrieval + Reranker 对比实验已完成。
- Day 6 负责将 Day 5 检索证据接入 Day 3 手写 ReAct 流程，完成固定通关测试。
- 后续开发必须遵守 `AGENTS.md` 的每日边界。

## 验证命令

在项目根目录准备虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

运行 Phase 0 已有测试：

```powershell
.\scripts\run_phase0_tests.ps1
```

已知基线：

- Day 1：`25 passed`
- Day 2：`31 passed`
- Day 3：`14 passed`
- Day 4：`13 passed`
- Day 5：`10 passed`

Day 1 到 Day 5 都存在独立运行边界，部分目录使用顶层 `app` 包名。测试必须在各自目录的独立进程中运行，不要直接从仓库根目录混跑 pytest。

## GitHub 接续

新账号接手时优先使用 GitHub 作为项目源：

```powershell
git clone https://github.com/nuzhishen/v20-phase0-survival.git
cd v20-phase0-survival
git status --short --branch
```

如果继续使用本机原目录：

```powershell
cd C:\ai\codex\v20-phase0-survival
git status --short --branch
git remote -v
```

预期 remote：

```text
origin  https://github.com/nuzhishen/v20-phase0-survival.git
```

如果新账号没有该 GitHub 仓库权限，需要用新账号 fork 或重新创建远端，再修改 remote。不要把账号令牌写入仓库文件。

## Codex 换账号注意事项

Codex 账号记忆是辅助召回层，不是项目交接源。当前项目的关键上下文已经固化在本仓库文档中，换账号后只需要重新打开项目并阅读必读文件。

不要迁移这些账号级或本机状态：

- `C:\Users\15814\.codex\auth.json`
- `C:\Users\15814\.codex\sessions\`
- `C:\Users\15814\.codex\plugins\cache\`
- `C:\Users\15814\AppData\Local\OpenAI\Codex\`
- 操作系统凭据管理器里的 Codex 凭据

可以参考但不要依赖这些本机状态：

- `C:\Users\15814\.codex\memories\`
- Codex App 左侧项目和对话列表
- 历史线程里的聊天记录

## 新账号第一条提示建议

```text
请先读取本仓库的 AGENTS.md、README.md、docs/account_switch_handoff.md、docs/day05_to_day06_handoff.md、day06_pass_test/README.md、day05_hybrid_rerank/docs/hybrid_vs_dense_report.md、day05_hybrid_rerank/docs/day05-what-blocked.md、day03_react_loop/app/react_loop.py 和 day03_react_loop/app/knowledge_base.py，作为当前上下文。继续开发时严格遵守 Phase 0 边界：不用 WebSocket、LangGraph、MCP、Redis、前端或平台化服务；Day 6 只把 Day 5 检索证据接入 Day 3 手写 ReAct 流程。
```

## 当前接续结论

本项目已经完成 Day 1 到 Day 5 的独立能力模块。账号切换或 Day 6 新会话时，项目连续性由 Git 仓库、`AGENTS.md`、`docs\day05_to_day06_handoff.md` 和各日文档保证，不由 Codex 账号记忆保证。
