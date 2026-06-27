# Day 4 阻塞记录

## 1. 哪个环节最不稳定？

最不稳定的是“短中文 Query 的语义相似度分数尺度”。

原因不是 Pipeline 断，而是 MockEmbedding 本身不是语义模型。纯字符重叠会把“今天、现在、怎么”这类常用词误判成弱相关，所以最终做了两层稳定化：

- Embedding 层：去掉中文单字特征，保留双字/三字/ASCII/业务关键词。
- Retriever 层：增加 `confidence_threshold=0.35`，有结果但最高分低时标记 `LOW_TOP_SCORE`。

这个问题也解释了为什么真实生产不能只看“有返回结果”，还要看 score、rank、domain、source 和失败样例。

## 2. 哪些 Query 没有命中预期 chunk？语义鸿沟案例是什么？

当前 `run_day04_eval.py` 的基线是 Recall@5 = 100.00%，但仍有 6 条没有 Top1 命中：

| Query ID | 领域 | 预期 chunk | 首中排名 | 主要问题 |
|---|---|---|---:|---|
| `tms_002` | TMS | `tms_e1002` | 2 | OTA 下载超时与 CDN 带宽异常存在共同词，纯 Dense 排序被干扰。 |
| `tms_004` | TMS | `tms_e1004` | 5 | “批量任务失败率高”与“脚本失败/回滚失败”共享失败语义。 |
| `tms_010` | TMS | `tms_e1010` | 2 | “时钟漂移/NTP”与固件版本问题的排查语言相似。 |
| `ott_004` | OTT | `ott_q004` | 4 | “灰屏/卡死”与黑屏、播放错误存在播放故障共性。 |
| `elderly_001` | 养老 | `elderly_001` | 3 | 高血压与睡眠、跌倒等主题共享“异常处理/联系医生”措辞。 |
| `elderly_007` | 养老 | `elderly_007` | 4 | 认知走失与跌倒、胸痛都含“立即联系家属/医生”的紧急处理语义。 |

典型语义鸿沟：

```text
用户：直播卡顿怎么排查？
文档：OTT 播放延迟高，检查 CDN 节点、用户带宽、播放器版本。
```

口语 Query 和书面文档在 Dense 空间中可能接近，也可能被“播放故障”这类宽泛语义稀释。Day 5 需要用 BM25/稀疏检索补住精确词，例如 `CDN`、`首帧`、`403`、`NTP`、`72小时`。

## 3. 哪些 chunk 切得太碎或太大？

当前没有出现无法评估的过碎或过大 chunk，但有两个后续要观察的点：

- TMS 每个异常码一个 chunk，结构完整，适合 Day 4；如果未来单个异常码扩展到多页，需要按“现象/排查/建议”做二级切分。
- 养老健康指南的 chunk 仍偏“主题段落”，为了保留禁忌和异常处理没有拆得很碎；Day 5 如果引入 BM25，可能需要把“正常范围/异常处理/禁忌”转成更清晰的字段。

当前每个领域都是 10 个 chunk，评估集 30 条 Query 能覆盖但不够大。Day 5 不应该只看总分，还要看每个失败样例的排序变化。

## 4. 哪些代码是 Cursor 辅助？哪些手写？

本轮按用户要求统一由 Codex 完成，没有使用 Cursor。

原计划里写“手写”的部分，本轮均由 Codex 按同等标准实现：

- 3 个 Chunker 核心逻辑。
- Qdrant Collection/HNSW/Payload index 配置。
- 30 条 Query 与 Ground Truth JSONL。
- 8 指标评估。
- No-answer/Fallback 兜底。
- 文档、流程图、复盘和交接材料。

## 5. HNSW 参数是否手动覆盖？

已手动覆盖，位置在 `app/qdrant_client.py`：

| 参数 | 值 | 说明 |
|---|---:|---|
| `m` | 16 | 每层最大连接数，平衡内存和召回。 |
| `ef_construct` | 100 | 构建时搜索深度，提升图质量。 |
| `hnsw_ef` | 64 | 查询时搜索深度，作为延迟和召回的折中。 |
| payload index | `domain` keyword | 支持 TMS/OTT/养老领域过滤。 |

当前客户端用 Qdrant REST API 实现，而不是 Python SDK，因为 Windows `.venv` 是 Python 3.14，SDK/依赖兼容性不如 REST 稳定。

## 6. 明天混合检索前最大的风险？

最大的风险是“指标提升看起来来自 reranker 或 BM25，但实际只是评估集被过拟合”。

明天建议用三组对照：

```text
Dense only
Sparse/BM25 only
Dense + Sparse + Reranker
```

每组都跑同一份 30 Query，并保留失败样例表。只报总分不够，必须回答：

- 哪些 Query 从未命中变成命中？
- 哪些 Query Top1 变差？
- 低分率是否下降？
- No-answer 是否仍然可靠？
- 平均延迟增加了多少？

## 7. Day 3 ReAct 替换准备

Day 3 当前的硬编码知识查询可以在 Day 6 替换为 RAG 检索接口，但今天不直接改 Day 3。

推荐替换形态：

```text
lookup_error_knowledge(error_code, symptom)
  -> Retriever.retrieve(query, domain="tms", top_k=5)
  -> 返回 chunk_id/source/title/text/score
```

必须保留 Day 3 安全边界：

- 低置信或无结果时返回 unknown，不让 Agent 编造。
- HIGH 风险或批量操作仍然进入 HITL。
- Qdrant 失败时使用 InMemory fallback，仍失败则 Observation 记录 tool error。
- ReAct 的 `Thought -> Action -> Observation -> Final` 主循环不交给框架。

## 今日三问

### 今天做出来什么？

完成了去框架化 RAG 检索底座：3 份语料、3 个切片器、Mock/BGE Embedding 抽象、Qdrant REST 客户端、Retriever、30 Query、8 指标、基线报告、Qdrant smoke 脚本、运行文档和交接文档。

### 今天学到了什么？

RAG 的关键不是“能返回文本”，而是：

- chunk 是否保持业务完整性；
- payload 是否能过滤领域；
- top_k 是否能解释来源；
- 低分结果是否被拒绝；
- 失败样例是否能指导下一天优化。

### 今天什么没做出来？

按 Day 4 边界，没有做混合检索、reranker、真实 LLM 生成、GraphRAG 或 Day 3 代码替换。BGE 已接入为可选 smoke，不把它放进单元测试主路径，避免外部模型影响稳定性。
