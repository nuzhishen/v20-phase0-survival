# Day 04: Minimal RAG Pipeline

## 目标

独立跑通最小检索链路：

```text
文档加载 -> 切片 -> Embedding -> Qdrant Upsert -> Search -> Top-K
```

数据覆盖 TMS 运维手册、OTT FAQ 和养老健康指南。

## 当前实现

- `app/chunker.py`：三种切片器，分别对应 TMS Markdown 异常码、OTT Q/A FAQ、养老健康固定长度+句界。
- `app/embedding.py`：`EmbeddingProvider` 抽象、确定性 `MockEmbedding`、WSL 侧 `BGEEmbedding`。
- `app/qdrant_client.py`：不依赖 Windows Python 3.14 里不可用的 SDK，直接用 Qdrant REST API；HNSW 参数和 Payload 索引手写。
- `app/retriever.py`：`query -> embed -> search -> top_k`，记录 latency，支持低置信标记和 InMemory fallback。
- `data/eval/rag_eval_queries.jsonl`：30 条评估 Query，覆盖 3 个领域，每条都有 Ground Truth。
- `tests/test_rag_pipeline.py`：覆盖 8 指标、Qdrant 请求形态、异常输入、fallback 和故障注入。

## 快速运行

```powershell
cd C:\ai\codex\v20-phase0-survival\day04_rag_pipeline
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe run_day04_eval.py
```

`run_day04_eval.py` 会生成：

```text
docs/rag_baseline_report.md
```

## Qdrant Smoke Test

Qdrant API Key 不写入仓库，运行前从环境变量读取：

```powershell
cd C:\ai\codex\v20-phase0-survival\day04_rag_pipeline
$env:QDRANT_URL = "http://localhost:6333"
$env:QDRANT_API_KEY = (wsl -e sh -lc "grep '^QDRANT_API_KEY=' ~/qdrant/qdrant.env | cut -d= -f2-")
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder mock
```

如果要验证真实 BGE 向量：

```powershell
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder bge --collection phase0_day4_context_bge_smoke
```

BGE 当前安装在 WSL：

```text
/home/aaron/venvs/v20-day4-bge/bin/python
```

选择放在 WSL 的原因：

- Windows 项目 `.venv` 是 Python 3.14，PyTorch/sentence-transformers 兼容性风险高。
- WSL Python 环境已验证有 `sentence-transformers`、`qdrant-client`、`torch CPU`。
- Day 4 默认测试仍使用 MockEmbedding，避免外部模型或网络影响 CI 稳定性。

## 必须完成

- 可重复的 Collection 配置。
- Chunk 元数据和来源标识。
- Top-K 检索结果包含证据来源。
- 30 条测试 Query 的基础评估数据。

## 禁止

- 不做 GraphRAG、多 Agent、复杂 Context Compression 或 RAG 平台。
- 不在本日加入 Reranker；Reranker 属于 Day 5。
