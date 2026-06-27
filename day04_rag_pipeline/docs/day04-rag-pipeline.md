# Phase 0 Day 4 RAG Pipeline 运行手册

## 1. 今日工程边界

Day 4 只实现并验证这一条链路：

```text
Load -> Chunk -> Embed -> Store -> Retrieve -> Evaluate
```

本日不做 LLM 生成、不做混合检索、不做 reranker、不做 GraphRAG、不接 LangChain/LlamaIndex 封装。这样做的理由很直接：检索质量必须先可重复、可量化，后续 Day 5/Day 6 才能判断混合检索和 Agent 替换是否真的提升。

## 2. 文件结构

```text
day04_rag_pipeline/
  app/
    schemas.py          # Pydantic 强类型：ChunkPayload / RetrievalResult / EvalMetrics
    chunker.py          # MarkdownChunker / QAChunker / FixedChunker
    embedding.py        # EmbeddingProvider / MockEmbedding / BGEEmbedding
    qdrant_client.py    # Qdrant REST 客户端，手写 HNSW 和 Payload index
    vector_store.py     # VectorStore 抽象 + InMemoryVectorStore 兜底
    retriever.py        # query -> embed -> search -> top_k + latency + low_confidence
    rag_pipeline.py     # 本地评估 Pipeline 和 8 指标计算
    documents.py        # 统一加载 3 份语料并选择切片器
  data/
    corpus/
      tms_ops_manual.md
      ott_ops_faq.md
      elderly_health_guide.md
    eval/
      rag_eval_queries.jsonl
  docs/
    rag_baseline_report.md
    day04-what-blocked.md
    day04-rag-flow.mmd
  tests/
    test_rag_pipeline.py
  run_day04_eval.py
  run_day04_qdrant_smoke.py
```

计划中写的是 `app/rag/*.py`，本项目按 Phase 0 既有规则使用每日独立顶层 `app` 包，避免 Day 1、Day 2、Day 3 的同名包互相污染。

## 3. 切片策略

| 领域 | 文件 | 切片器 | 选择理由 |
|---|---|---|---|
| TMS | `tms_ops_manual.md` | `MarkdownChunker` | 异常码是天然边界，不能把 E1001 的现象、排查、建议拆散。 |
| OTT | `ott_ops_faq.md` | `QAChunker` | FAQ 的最小知识单元是一问一答，Query 通常匹配 Q 或 A 中的指标词。 |
| 养老健康 | `elderly_health_guide.md` | `FixedChunker` | 健康指南结构较弱，固定长度要结合句界，避免切断血压、剂量、禁忌。 |

所有 chunk 都写入稳定字段：

```text
chunk_id, domain, source, title, text, metadata
```

`domain` 只能是 `tms | ott | elderly`，未知字段和隐式类型转换都会被 Pydantic 拒绝。

## 4. Embedding 决策

### 默认：MockEmbedding

默认测试使用 `MockEmbedding`，因为它具备三个工程性质：

- 确定性：同一段文本永远生成同一向量。
- 无外部依赖：不依赖网络、GPU、模型缓存或 Qdrant。
- 可评估：适合锁定 chunk、upsert、search、top_k、fallback 和 8 指标逻辑。

MockEmbedding 不是语义模型，不声称能替代 BGE。它只是 Day 4 的稳定基线。

### 真实向量：BGEEmbedding

BGE 放在 WSL，不放在 Windows 本机 `.venv`：

```text
/home/aaron/venvs/v20-day4-bge/bin/python
```

选择 WSL 的原因：

- Windows 项目 `.venv` 是 Python 3.14，PyTorch/sentence-transformers 兼容性风险高。
- WSL 环境已安装并验证 `sentence-transformers`、`qdrant-client`、`torch CPU`。
- BGE 通过子进程调用，不影响 Windows 项目的测试稳定性。

## 5. Qdrant 配置

Qdrant 客户端在 `app/qdrant_client.py` 中使用 REST API，不依赖 Python SDK。核心参数如下：

| 参数 | 当前值 | 含义 |
|---|---:|---|
| distance | Cosine | 与向量归一化策略一致。 |
| hnsw `m` | 16 | 每个节点的最大连接数，平衡构建成本和召回。 |
| hnsw `ef_construct` | 100 | 构图时搜索深度，提高图质量但增加构建时间。 |
| query `hnsw_ef` | 64 | 查询时搜索深度，平衡延迟和召回。 |
| payload index | `domain` keyword | 支持按领域过滤，避免 TMS/OTT/养老互相污染。 |
| batch size | 100 | upsert 分批写入，避免单次请求过大。 |

API Key 不写入仓库。运行 smoke test 时从环境变量读取：

```powershell
$env:QDRANT_URL = "http://localhost:6333"
$env:QDRANT_API_KEY = (wsl -e sh -lc "grep '^QDRANT_API_KEY=' ~/qdrant/qdrant.env | cut -d= -f2-")
```

## 6. 运行命令

### 单元测试

```powershell
cd C:\ai\codex\v20-phase0-survival\day04_rag_pipeline
..\.venv\Scripts\python.exe -m pytest -q
```

### 生成评估报告

```powershell
..\.venv\Scripts\python.exe run_day04_eval.py
```

输出：

```text
docs/rag_baseline_report.md
```

### Qdrant Mock Smoke

```powershell
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder mock
```

### Qdrant + BGE Smoke

```powershell
..\.venv\Scripts\python.exe run_day04_qdrant_smoke.py --embedder bge --collection phase0_day4_context_bge_smoke
```

BGE 会加载真实模型，首次运行可能明显慢于 Mock。

本机已完成一次真实 smoke：

| 模式 | Collection | 结果 |
|---|---|---|
| Mock + Qdrant | `phase0_day4_context_smoke` | 通过，TMS/OTT/养老均返回非低置信 Top-K。 |
| BGE + Qdrant | `phase0_day4_context_bge_smoke` | 通过，BGE 返回 512 维中文向量，三类领域均完成检索。 |

## 7. 当前基线

以 `run_day04_eval.py` 生成的报告为准：

| 指标 | 当前结果 |
|---|---:|
| Recall@1 | 80.00% |
| Recall@3 | 90.00% |
| Recall@5 | 100.00% |
| MRR | 0.8678 |
| Context Precision@5 | 94.00% |
| No-answer/Fallback | 100.00% |
| 低分率 | 3.33% |
| 平均检索延迟 | 0.49 ms |

这些数字是 Mock + InMemory 的稳定工程基线，不代表真实 BGE 的最终线上效果。

## 8. Day 3 ReAct 衔接

Day 3 的硬编码知识查询可以在 Day 6 替换为：

```text
lookup_error_knowledge(error_code, symptom)
  -> Retriever.retrieve(query, domain="tms", top_k=5)
  -> 只把 chunk_id/source/title/text/score 作为证据交给 ReAct
```

替换时必须保留 Day 3 的安全边界：

- 高风险操作继续 HITL。
- 未命中或低置信不得编造处置建议。
- tool error 必须进入 Observation。
- `max_steps=6` 的 ReAct 控制流不被 RAG 改写。
