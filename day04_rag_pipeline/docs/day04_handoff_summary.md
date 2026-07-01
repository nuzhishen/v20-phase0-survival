# Day 4 交接总结

## 当前状态

Day 4 下午到晚上的源码与文档已完成，默认链路可在本地独立运行：

```text
chunk -> embed -> upsert -> search -> top_k -> evaluate
```

核心验证结果：

```text
pytest: 13 passed
Recall@5: 100.00%
Context Precision@5: 94.00%
No-answer/Fallback: 100.00%
平均检索延迟: 0.49 ms
```

## 已完成的交付物

| 类型 | 路径 | 说明 |
|---|---|---|
| 源码 | `app/chunker.py` | 3 个切片器：TMS Markdown、OTT Q/A、养老固定+句界。 |
| 源码 | `app/embedding.py` | Mock/BGE Embedding 抽象，BGE 通过 WSL Python 调用。 |
| 源码 | `app/qdrant_client.py` | Qdrant REST 客户端，HNSW 和 Payload index 手写。 |
| 源码 | `app/retriever.py` | 检索 Pipeline、latency、low confidence、fallback。 |
| 源码 | `app/rag_pipeline.py` | 本地 Pipeline 和 8 指标评估。 |
| 数据 | `data/corpus/*.md` | TMS/OTT/养老各 10 条业务语料。 |
| 数据 | `data/eval/rag_eval_queries.jsonl` | 30 条 Query + Ground Truth。 |
| 测试 | `tests/test_rag_pipeline.py` | 单元测试、指标测试、Qdrant 请求形态、异常路径。 |
| 脚本 | `run_day04_eval.py` | 生成基线报告。 |
| 脚本 | `run_day04_qdrant_smoke.py` | 真实 Qdrant smoke，可选 Mock/BGE。 |
| 文档 | `docs/rag_baseline_report.md` | 真实指标报告。 |
| 文档 | `docs/day04-rag-pipeline.md` | 运行手册。 |
| 文档 | `docs/day04-rag-flow.mmd` | Mermaid 全链路图。 |
| 文档 | `docs/day04-what-blocked.md` | 7 个阻塞问题与今日三问。 |
| 文档 | `docs/day04_evening_review_interview_talktrack.md` | 晚间复盘和面试话术。 |

## Qdrant 与 BGE

Qdrant：

- 本机默认 URL：`http://localhost:6333`
- 局域网 URL：`http://192.168.28.151:6333`
- API Key 不写仓库，运行时动态读取。
- collection 默认 smoke 名称：`phase0_day4_context_smoke`
- 已验证 Mock + Qdrant smoke：TMS/OTT/养老均返回非低置信 Top-K。
- 2026-07-01 修复：直接运行 smoke 脚本时，如果 Windows PowerShell 没有 `QDRANT_API_KEY`，旧逻辑会触发 Qdrant `401`。
- 当前 `run_day04_qdrant_smoke.py` 的 API Key 读取优先级：
  1. 命令行 `--api-key`
  2. Windows 当前进程环境变量 `QDRANT_API_KEY`
  3. WSL 文件 `~/qdrant/qdrant.env`

推荐验证命令：

```powershell
cd C:\ai\codex\v20-phase0-survival\day04_rag_pipeline
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder mock
```

强制走局域网地址：

```powershell
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder mock --url http://192.168.28.151:6333
```

BGE：

- 安装位置：WSL `/home/aaron/venvs/v20-day4-bge/bin/python`
- 默认测试不依赖 BGE。
- 真实向量验证使用 `run_day04_qdrant_smoke.py --embedder bge`。
- 已验证中文 BGE 向量：512 维。
- 已验证 BGE + Qdrant smoke：collection `phase0_day4_context_bge_smoke` 可写入并检索。

真实 BGE 验证命令：

```powershell
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder bge --collection phase0_day4_context_bge_smoke
```

## 下轮建议

Day 5 不要重写 Day 4。建议只新增混合检索层，并保留 Day 4 作为 Dense baseline：

```text
Dense only: 当前 Day 4
Sparse only: 新增 BM25 或等价稀疏检索
Hybrid: Dense + Sparse merge
Reranker: 在 Hybrid Top-K 后重排
```

必须复用同一份 `data/eval/rag_eval_queries.jsonl`，否则无法证明 Day 5 指标提升来自检索策略，而不是换了评估集。

## Day 6 衔接提醒

Day 6 替换 Day 3 硬编码知识库时，只替换知识查询动作，不替换 ReAct 控制流：

```text
lookup_error_knowledge()
  -> Retriever.retrieve(domain="tms")
  -> evidence chunks
  -> Day 3 ReAct Observation
```

低置信、无结果或 Qdrant 失败都不能生成处置结论，必须保持 Day 3 的 unknown fallback 和 HITL 规则。
