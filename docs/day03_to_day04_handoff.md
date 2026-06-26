# Day 03 -> Day 04 Handoff

交接日期：2026-06-26  
当前仓库：`https://github.com/nuzhishen/v20-phase0-survival`  
当前分支：`main`

## 新会话第一步

第四天新开会话或新项目时，先读取这些文件：

1. `AGENTS.md`
2. `README.md`
3. `docs/account_switch_handoff.md`
4. `docs/day03_to_day04_handoff.md`
5. `day03_react_loop/docs/react_accuracy_report.md`
6. `day03_react_loop/docs/day03-what-blocked.md`
7. `day04_rag_pipeline/README.md`

建议第一条提示：

```text
请先读取 AGENTS.md、README.md、docs/day03_to_day04_handoff.md、day03_react_loop/docs/react_accuracy_report.md、day03_react_loop/docs/day03-what-blocked.md、day04_rag_pipeline/README.md，作为 Day 4 上下文。继续严格遵守 Phase 0 边界：Day 4 只做 chunk -> embed -> upsert -> search -> top_k，不做 GraphRAG、多 Agent、复杂 Context Compression、Reranker、前端、MCP、Redis 或 LangGraph。
```

## Day 3 完成状态

Day 3 已完成规则版最小 ReAct 状态机，绑定 TMS 异常诊断场景。

核心产物：

- `day03_react_loop/app/react_types.py`
- `day03_react_loop/app/knowledge_base.py`
- `day03_react_loop/app/tools.py`
- `day03_react_loop/app/react_loop.py`
- `day03_react_loop/tests/test_react_loop.py`
- `day03_react_loop/docs/transformer_kv_cache_react_notes.md`
- `day03_react_loop/docs/react_accuracy_report.md`
- `day03_react_loop/docs/day03-what-blocked.md`

核心能力：

- `Thought -> Action -> Observation -> Final` 规则状态流转。
- `max_steps=6` 安全终止。
- ToolRegistry 白名单。
- 未知异常码不胡编，进入人工排查。
- 工具异常转 Observation，不让 Agent 崩溃。
- HIGH 风险或 `batch_size > 100` 触发 HITL。
- 设备离线时暂缓远程 OTA。

## Day 3 验证基线

单独运行 Day 3：

```powershell
cd C:\ai\codex\v20-phase0-survival\day03_react_loop
..\.venv\Scripts\python.exe -m app.react_loop
..\.venv\Scripts\python.exe -m pytest -q
```

当前结果：

```text
14 passed in 0.04s
```

跨日验证：

```powershell
cd C:\ai\codex\v20-phase0-survival
.\scripts\run_phase0_tests.ps1
```

当前结果：

```text
Day 1: 25 passed, 1 warning
Day 2: 31 passed
Day 3: 14 passed
```

指标：

| 指标 | 当前结果 |
|---|---:|
| 决策准确率 | 100% (10/10) |
| 幻觉率 | 0% (0/1) |
| 拒绝率 | 100% (5/5) |
| HITL 触发准确率 | 100% (5/5) |

## Day 3 已知风险

Day 3 的能力是规则版状态机，不是生产 Agent。

主要风险：

- `knowledge_base.py` 是硬编码知识库，覆盖面有限。
- `estimate_operation_risk()` 阈值仍是训练规则，需要更多样例校准。
- 设备离线会改写推荐动作，但尚未作为独立风险工具输入。
- 未来接入真实 LLM 后，仍需限制 Thought 长度、历史轮数和工具 Schema，避免 Token 膨胀。

Day 4 不能删除的安全边界：

- 检索为空不能胡编。
- 未知异常码兜底要保留。
- 高风险操作仍然要 HITL。
- ReAct 不应因为检索结果低质量而直接建议 OTA、脚本或重启。

## Day 4 目标

Day 4 只实现最小 RAG Pipeline：

```text
文档加载 -> 切片 -> Embedding -> Qdrant Upsert -> Search -> Top-K
```

必须完成：

- 可重复的 Collection 配置。
- Chunk 元数据和来源标识。
- Top-K 检索结果包含证据来源。
- 30 条测试 Query 的基础评估数据。

禁止：

- 不做 GraphRAG。
- 不做多 Agent。
- 不做复杂 Context Compression。
- 不做 RAG 平台。
- 不加入 Reranker；Reranker 属于 Day 5。
- 不把 Day 3 的 ReAct 循环扩成 LangGraph。

## Day 4 推荐实现口径

建议新增在 `day04_rag_pipeline/` 内：

```text
app/
  rag_types.py
  documents.py
  chunking.py
  embeddings.py
  vector_store.py
  rag_pipeline.py
tests/
  test_rag_pipeline.py
docs/
  rag_eval_baseline.md
  day04_handoff_summary.md
```

建议先使用可测试的本地 Mock Embedding 或确定性 Embedding，保证训练链路稳定；如果使用 Qdrant，也必须让测试不依赖外部服务。

Day 4 的关键不是模型效果，而是证据链：

```text
query -> top_k chunks -> source metadata -> answer/evidence boundary
```

## Git 状态

Day 3 代码已提交并推送：

```text
6871f4c phase0-day3 manual react state machine
```

第四天开始前建议执行：

```powershell
git pull --ff-only
git status --short --branch
.\scripts\run_phase0_tests.ps1
```
