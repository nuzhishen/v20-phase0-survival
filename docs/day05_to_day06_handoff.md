# Day 05 -> Day 06 Handoff

交接日期：2026-07-07
当前仓库：`https://github.com/nuzhishen/v20-phase0-survival`
当前分支：`main`

## 新会话第一步

第六天新开会话时，先读取这些文件：

1. `AGENTS.md`
2. `README.md`
3. `docs/account_switch_handoff.md`
4. `docs/day05_to_day06_handoff.md`
5. `day06_pass_test/README.md`
6. `day05_hybrid_rerank/docs/hybrid_vs_dense_report.md`
7. `day05_hybrid_rerank/docs/day05-what-blocked.md`
8. `day05_hybrid_rerank/tests/test_hybrid_retrieval.py`
9. `day03_react_loop/app/react_loop.py`
10. `day03_react_loop/app/knowledge_base.py`

建议第一条提示：

```text
请先读取 AGENTS.md、README.md、docs/day05_to_day06_handoff.md、day06_pass_test/README.md、day05_hybrid_rerank/docs/hybrid_vs_dense_report.md、day05_hybrid_rerank/docs/day05-what-blocked.md、day03_react_loop/app/react_loop.py 和 day03_react_loop/app/knowledge_base.py，作为 Day 6 上下文。继续严格遵守 Phase 0 边界：Day 6 只把 Day 5 检索证据接入 Day 3 手写 ReAct 流程，不引入 LangGraph、GraphRAG、Query Rewrite、MCP、Redis、前端或真实 OTA/脚本操作。
```

## Day 5 完成状态

Day 5 已完成 Dense vs Sparse/BM25 vs Hybrid vs Reranker 的可量化对比。

核心提交：

```text
3f369cf docs: add day5 morning hybrid retrieval notes
8ab34b7 phase0-day5 hybrid retrieval reranker comparison
```

核心产物：

- `day05_hybrid_rerank/app/rag/types.py`
- `day05_hybrid_rerank/app/rag/data_loader.py`
- `day05_hybrid_rerank/app/rag/dense_retriever.py`
- `day05_hybrid_rerank/app/rag/sparse_retriever.py`
- `day05_hybrid_rerank/app/rag/hybrid_fusion.py`
- `day05_hybrid_rerank/app/rag/hybrid_retriever.py`
- `day05_hybrid_rerank/app/rag/reranker.py`
- `day05_hybrid_rerank/app/rag/compare_eval.py`
- `day05_hybrid_rerank/tests/test_hybrid_retrieval.py`
- `day05_hybrid_rerank/docs/hybrid_vs_dense_report.md`
- `day05_hybrid_rerank/docs/day05-what-blocked.md`

## 1. Day 5 当天工作如何验证

### 单独验证 Day 5

```powershell
cd C:\ai\codex\v20-phase0-survival\day05_hybrid_rerank
..\.venv\Scripts\python.exe -m pytest -q
```

期望结果：

```text
10 passed
```

### 重新生成 Day 5 对比报告

```powershell
cd C:\ai\codex\v20-phase0-survival\day05_hybrid_rerank
..\.venv\Scripts\python.exe -m app.rag.compare_eval
```

期望输出包含：

```text
report=C:\ai\codex\v20-phase0-survival\day05_hybrid_rerank\docs\hybrid_vs_dense_report.md
blocked=C:\ai\codex\v20-phase0-survival\day05_hybrid_rerank\docs\day05-what-blocked.md
dense_recall_at_3=0.9000
best_final=Best Hybrid + MockReranker (Hybrid alpha=0.6)
best_final_recall_at_3=1.0000
best_final_mrr=1.0000
```

注意：报告里的平均延迟是本机运行时指标，允许小幅波动。关键稳定指标是 Dense baseline、Recall@3、MRR 和最终配置。

### 验证完整 Phase 0

```powershell
cd C:\ai\codex\v20-phase0-survival
.\scripts\run_phase0_tests.ps1
```

期望：Day 1 到 Day 5 全部通过。由于每一天都有独立顶层 `app` 包，必须使用脚本分目录运行，不要在仓库根目录直接混跑 pytest。

## 2. Day 5 代码入口和查看顺序

建议按下面顺序看源码，不要从 `compare_eval.py` 直接跳进所有细节：

1. `day05_hybrid_rerank/docs/hybrid_vs_dense_report.md`
   先看最终结论、指标、推荐配置和面试话术。

2. `day05_hybrid_rerank/docs/day05-what-blocked.md`
   看当天复盘、退化风险、BGE 未接入原因、MockReranker 兜底方式。

3. `day05_hybrid_rerank/app/rag/types.py`
   看 Day 5 的核心数据结构：`Chunk`、`EvalQuery`、`SearchResult`。

4. `day05_hybrid_rerank/app/rag/data_loader.py`
   看 Day 5 如何读取 Day 4 语料和 `rag_eval_queries.jsonl`，这是跨日复用边界。

5. `day05_hybrid_rerank/app/rag/dense_retriever.py`
   看 Dense baseline。重要边界：只嵌入 `chunk.text`，不要把 title/metadata 拼进去，否则会污染 Day 4 基线。

6. `day05_hybrid_rerank/app/rag/sparse_retriever.py`
   看 BM25 和 tokenizer，重点是错误码、Android 版本、设备型号、403、NTP、CDN 等精确 token 的保留。

7. `day05_hybrid_rerank/app/rag/hybrid_fusion.py`
   看三种融合：`fuse_weighted()`、`fuse_linear()`、`fuse_rrf()`。Day 5 实验主用 alpha 加权与 RRF。

8. `day05_hybrid_rerank/app/rag/hybrid_retriever.py`
   看统一入口 `HybridRetriever.search()`：Dense + Sparse -> Fusion -> optional Reranker。

9. `day05_hybrid_rerank/app/rag/reranker.py`
   看 `MockReranker`、`BGEReranker` 占位和 `FallbackReranker`。Day 5 默认不依赖真实模型。

10. `day05_hybrid_rerank/app/rag/compare_eval.py`
    最后看评估入口：它跑 Dense、Sparse、alpha grid、RRF、Best+MockReranker，并生成两份文档。

11. `day05_hybrid_rerank/tests/test_hybrid_retrieval.py`
    看行为约束：tokenizer、empty query、alpha 边界、RRF、reranker fallback、30 条 eval 复用、对比脚本入口。

## Day 5 最终技术结论

最终推荐配置：

```text
Best Hybrid + MockReranker (Hybrid alpha=0.6)
```

关键指标：

| Method | Recall@3 | MRR | 说明 |
|---|---:|---:|---|
| Dense Only | 90.00% | 0.8678 | Day 4 对照基线 |
| Hybrid alpha=0.6 | 100.00% | 0.9833 | 最优 Hybrid |
| Best Hybrid + MockReranker | 100.00% | 1.0000 | Day 6 推荐检索层 |

技术判断：

```text
Dense 负责语义召回，Sparse/BM25 负责错误码、设备型号、Android 版本和精确术语召回。Day 5 用 alpha=0.6 的 Hybrid 融合与 MockReranker 精排 TopN，换来 Recall@3 和 MRR 提升；代价是复杂度和延迟上升，必须继续保留退化率、延迟和 fallback 监控。
```

## Day 6 接入建议

Day 6 的目标不是继续改检索算法，而是把 Day 5 的检索证据接入 Day 3 的手写 ReAct 流程。

建议新增一个 Day 6 内部适配层，例如：

```text
day06_pass_test/app/
  evidence_retriever.py
  diagnosis_flow.py
  schemas.py
tests/
  test_day06_pass_test.py
```

适配层职责：

- 调用 Day 5 的最终配置：Dense + Sparse + Weighted alpha=0.6 + MockReranker。
- 输入固定 pass-test query：`OTA_TIMEOUT`、设备离线、华南、近 7 天失败率 0.18。
- 输出证据列表：`chunk_id`、`source`、`title`、`text`、`score`、`method_scores`。
- 把证据交给 Day 3 风格的决策流，但不让检索结果直接绕过安全判断。

Day 6 必须保留的 Day 3 安全边界：

- 未知异常码不胡编，进入人工排查。
- 工具异常转 Observation，不让流程崩溃。
- HIGH 风险或批量操作触发 HITL。
- 设备离线时暂缓远程 OTA。
- 低置信、无检索结果或证据不足时进入 fallback，不强行给高风险动作。

Day 6 禁止事项：

- 不做 Query Rewrite。
- 不做 GraphRAG。
- 不接 LangGraph。
- 不做前端或平台化服务。
- 不执行真实 OTA、真实脚本或真实重启。
- 不因为 Reranker Top1 好看就删除 HITL。

## Day 6 通过标准映射

来自 `day06_pass_test/README.md` 的固定链路：

```text
输入校验
-> RAG 检索 OTA 运维手册
-> ReAct 查询设备状态
-> 风险评估
-> HITL 判断
-> 结构化 DiagnosisResult
```

Day 5 对它的贡献是第二步：提供可解释、有来源、可降级的 RAG 检索证据。Day 3 对它的贡献是后四步：状态机、工具白名单、风险评估、HITL 和结构化结果。

## 第六天开始前检查清单

- [ ] `git pull --ff-only`
- [ ] `git status --short --branch`
- [ ] `.\scripts\run_phase0_tests.ps1`
- [ ] 重读 `docs/day05_to_day06_handoff.md`
- [ ] 确认 Day 5 报告仍是 Dense Recall@3 90.00%、Final Recall@3 100.00%、MRR 1.0000
- [ ] Day 6 只做集成，不继续扩大检索算法范围
