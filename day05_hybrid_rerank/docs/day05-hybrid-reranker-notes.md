# Day 5 Hybrid Retrieval + Reranker 原理笔记

> 范围：Phase 0 Day 5 08:30-11:00 原理 / 面试攻击点整理稿。
> 目标：解释为什么 Day 4 的纯 Dense baseline 需要升级为 Sparse/BM25 + Hybrid Fusion + Reranker，并明确今日不扩展 Query Rewrite、GraphRAG 或 ReAct 深集成。

## 0. 今日技术判断

在生产级 RAG 系统中，Dense Retrieval 不能单独承担全部召回，因为 TMS 场景存在大量错误码、设备型号、Android 版本和精确术语。我的设计选择是用 Dense 负责语义召回、Sparse/BM25 负责关键词召回，再通过 RRF 或 alpha 加权融合，并只对候选 TopN 做 Reranker 重排。代价是延迟和复杂度上升，收益必须用 Recall、MRR、退化率和延迟数据验证。

这句话背后有三个工程前提：

- Day 4 已经有 Dense baseline，不能覆盖或重写。
- Day 5 必须复用同一份 30 条 Query，否则指标不可比较。
- Hybrid 是否更好要靠实验，不靠“混合一定更强”的直觉。

## 1. BM25 / Sparse Retrieval

### 1.1 BM25 公式

对 query `q` 和文档 `d`，BM25 的常见形式是：

```text
BM25(q, d) =
  sum over t in q:
    IDF(t) * ( TF(t,d) * (k1 + 1) )
             / ( TF(t,d) + k1 * (1 - b + b * |d| / avgdl) )
```

其中：

```text
IDF(t) = ln( 1 + (N - df(t) + 0.5) / (df(t) + 0.5) )
```

变量解释：

| 符号 | 含义 | 工程直觉 |
|---|---|---|
| `t` | query 中的一个 term | 例如 `E1002`、`OTA_TIMEOUT`、`Android 5.5`、`CDN` |
| `TF(t,d)` | term 在文档 `d` 中出现次数 | 出现越多，相关性越强，但 BM25 会让它饱和 |
| `IDF(t)` | term 的逆文档频率 | 越稀有越重要，错误码和版本号通常 IDF 高 |
| `N` | 文档总数 | 当前 Day 4 语料每域约 10 个 chunk |
| `df(t)` | 包含 term 的文档数 | `CDN` 出现在多条文档里，`E1009` 只在一条里 |
| `|d|` | 文档长度 | 长文档天然包含更多词，需要归一化 |
| `avgdl` | 平均文档长度 | 用于判断当前文档是否偏长 |
| `k1` | TF 饱和参数 | 越大越相信重复出现，常见范围约 `1.2-2.0` |
| `b` | 文档长度归一化参数 | `0` 不惩罚长文档，`1` 强归一化，常用 `0.75` |

### 1.2 k1 的作用

`k1` 控制词频增长的“边际收益”。

如果 query term 是 `CDN`，某个 chunk 里出现 1 次说明可能相关，出现 3 次通常更相关；但出现 30 次不应该比 3 次强十倍。BM25 用 `k1` 让 TF 贡献逐渐饱和，避免高频词把排序完全占满。

TMS/OTT/养老语料都不长，初始实现可用默认值 `k1=1.5`。如果后续出现长手册、日志段落或重复表格，再用评测集调参。

### 1.3 b 的作用

`b` 控制文档长度惩罚。

如果 `b=0`，长 chunk 不会被惩罚，可能因为包含词多而更容易得分高。如果 `b=1`，长文档会被强烈归一化，防止“大而全”chunk 挤掉更精准的短 chunk。

Day 4 的 chunk 比较短且结构规整，`b=0.75` 是合理起点。Day 5 不应该为了单个失败样例随意调 `b`，否则容易过拟合 30 条 Query。

### 1.4 为什么 BM25 还有价值

Dense 检索擅长语义泛化，但它对精确符号不稳定。BM25 的价值是：

- 精确匹配可靠：`E1002`、`OTA_TIMEOUT`、`403`、`NTP`、`Android Player 5.5` 命中就有明确解释。
- 短 query 友好：用户只输入“播放地址 403”时，Sparse 比 Dense 更容易锁定 `403`。
- 专有名词不被语义稀释：设备型号、固件版本、播放器版本不应被当作普通文本。
- 冷启动简单：不依赖模型下载、GPU、向量维度或 embedding 质量。

## 2. Dense vs Sparse 六维对比

| 维度 | Dense Retrieval | Sparse/BM25 Retrieval | Day 5 判断 |
|---|---|---|---|
| 语义理解 | 能理解同义和改写，例如“卡顿”接近“播放延迟” | 主要依赖词面重合，不懂深层语义 | Dense 负责语义召回 |
| 精确匹配 | 对编号、版本、错误码可能被向量空间稀释 | 对 `E1002`、`403`、`Android 5.5` 等命中稳定 | Sparse 负责术语召回 |
| 错误码/型号/版本 | `TMS-GD-200`、`Android 11` 可能被当普通 token | 可以用正则和分词保留完整符号 | TMS 必须引入 Sparse |
| 成本 | 建库要跑 embedding，真实 BGE 有环境成本 | 建倒排索引便宜，纯 CPU 即可 | Sparse 是低成本补充 |
| 延迟 | ANN 检索快，但依赖向量库和查询 embedding | 小语料 BM25 很快，大语料依赖倒排索引 | 两者合并会增加一些延迟 |
| 冷启动 | 需要 embedding 模型、向量维度、collection 配置 | 只要文本和 tokenizer 就能跑 | Day 5 默认路径应本地可测 |

结论：Dense 和 Sparse 不是替代关系，而是互补关系。Dense 解决“用户说法和文档说法不完全一致”，Sparse 解决“用户给了明确术语但 Dense 排序不稳”。

## 3. TMS 场景为什么需要 Sparse

TMS 不是纯自然语言问答，它包含大量机器符号和运维术语：

- 错误码：`E1001`、`E1002`、`OTA_TIMEOUT`、`SCRIPT_EXEC_ERROR`。
- 设备型号：`TMS-GD-100`、`TMS-GD-200`、`TMS-HD-300`。
- Android 版本：`Android 10`、`Android 11`、`Android Player 5.5`。
- 组件和协议：`EMQX`、`MQTT`、`JWT`、`ACL`、`CDN`、`NTP`。
- 风险阈值：`72 小时`、`10%`、`100 台`、`300MB`、`800MB`。

这些信息的特点是“精确值本身就是证据”。例如：

```text
query: OTA 下载卡在 60% 并提示 timeout 怎么办？
expected: tms_e1002
Sparse 关键点: OTA / 下载 / timeout / CDN / 60%
Dense 风险: 可能被“CDN 命中率过低”或“存储空间不足”这类相近排查语言干扰。
```

再例如：

```text
query: 设备时间漂移 10 分钟影响证书校验怎么办？
expected: tms_e1010
Sparse 关键点: 时间漂移 / 10 分钟 / 证书 / NTP
Dense 风险: 证书校验也可能拉近 EMQX 认证失败相关 chunk。
```

因此 Day 5 的 Sparse 检索必须保留错误码、版本号、百分比、容量单位、协议名和英文 token，不能用粗糙中文分词把它们拆碎。

## 4. 三种融合策略

### 4.1 RRF

RRF 是 Reciprocal Rank Fusion，基于排名而不是原始分数融合：

```text
RRF(d) = sum over retriever m:
  1 / (k + rank_m(d))
```

其中：

- `rank_m(d)` 是文档 `d` 在检索器 `m` 里的排名，从 1 开始。
- `k` 是平滑常数，常用 `60`。
- 如果文档只在一个检索器里出现，也能得到分数。

适用场景：

- Dense score 和 BM25 score 尺度差异大，不适合直接相加。
- 只想利用“两个检索器都认为它靠前”的排序信号。
- 初始 Hybrid 实验还没有稳定的 score calibration。

RRF 的好处是稳健，坏处是丢掉了分数间距信息。例如第 1 名和第 2 名差距很大，RRF 仍只把它们看作相邻排名。

### 4.2 加权求和

加权求和需要先把 Dense 和 Sparse 分数归一化：

```text
dense_norm(d)  = normalize(dense_score(d))
sparse_norm(d) = normalize(sparse_score(d))

hybrid_score(d) =
  alpha * dense_norm(d) + (1 - alpha) * sparse_norm(d)
```

其中：

- `alpha=0.2`：偏 Sparse。
- `alpha=0.4`：Sparse 略强。
- `alpha=0.5`：平衡。
- `alpha=0.6`：Dense 略强。
- `alpha=0.8`：偏 Dense。

适用场景：

- 分数已经做了 per-query normalize。
- 想明确控制 Dense 与 Sparse 的权重。
- 需要通过 grid search 找最优 alpha。

Day 5 不能拍脑袋固定 `alpha`。必须用同一 30 条 Query 跑 `0.2/0.4/0.5/0.6/0.8`，比较 Recall@1、Recall@3、MRR、Context Precision、退化率和平均延迟。

### 4.3 线性插值

线性插值可以看作更强调校准后的融合形式：

```text
score_linear(d) =
  beta0 + beta_dense * calibrated_dense(d) + beta_sparse * calibrated_sparse(d)
```

如果不使用偏置项，也可写成：

```text
score_linear(d) =
  lambda * calibrated_dense(d) + (1 - lambda) * calibrated_sparse(d)
```

它和普通加权求和的区别在于：线性插值更适合在有验证集或历史点击数据时校准权重，让 `beta_dense`、`beta_sparse` 来自数据，而不是手动试参。

适用场景：

- 有足够验证集，可以学习或稳定选择权重。
- Dense/BM25 分数已经校准到可比较尺度。
- 需要后续扩展更多特征，例如 domain boost、title hit、error_code exact match。

Day 5 当前只有 30 条 Query，不适合训练复杂权重模型。因此线性插值可以作为公式和后续方向理解，上午实现优先级应低于 RRF 与 alpha 加权。

## 5. Hybrid 权重怎么定

权重不能靠直觉，必须靠同一评测集对比。

Day 5 的最小权重实验：

```text
alpha = [0.2, 0.4, 0.5, 0.6, 0.8]
top_k = 5
candidate_pool = top 10 or top 20
eval_set = Day 4 的 30 条 Query
```

每个 alpha 至少统计：

- Recall@1：Top1 是否命中预期 chunk。
- Recall@3：Top3 是否命中，直接影响 Reranker 候选质量。
- MRR：正确证据排得越靠前越好。
- Context Precision@5：相关证据是否靠前。
- Hit Rate@3：Top3 是否包含预期证据。
- 平均延迟：Hybrid 不能为了小幅指标提升带来不可接受延迟。
- 退化率：Hybrid 排名低于 Dense 的 Query 比例。

选择最优配置时，不只看总分最高，还要看退化样例。如果某个 alpha 让 TMS 错误码更好，但让养老健康大幅变差，就不能直接作为 Day 6 默认配置。

## 6. Reranker 机制

### 6.1 Bi-Encoder

Bi-Encoder 分别编码 query 和文档：

```text
query -> vector_q
doc   -> vector_d
score = cosine(vector_q, vector_d)
```

优点：

- 文档向量可提前离线计算。
- 全库 ANN 检索快。
- 适合第一阶段召回。

缺点：

- query 和 doc 独立编码，交互弱。
- 对细粒度条件、否定、数值、版本匹配不够敏感。
- 容易把“语义相近但条件不同”的 chunk 排前。

### 6.2 Cross-Encoder

Cross-Encoder 把 query 和候选文档一起输入模型：

```text
[query, document] -> model -> relevance_score
```

优点：

- query 与候选文本充分交互。
- 更能判断“这个 chunk 是否真的回答了这个 query”。
- 对排序改善通常比单纯 Dense 更强。

缺点：

- 每个候选都要跑一次模型前向计算。
- 不能对全库直接使用，成本和延迟太高。
- 候选里没有正确 chunk 时，它无法凭空召回。

### 6.3 Reranker 的位置

正确位置：

```text
query
 -> Dense topN
 -> Sparse topN
 -> Hybrid fusion candidate_pool
 -> Reranker rerank TopN
 -> final topK
```

Reranker 不是第一阶段检索器。它的职责是“重排候选”，不是“全库找候选”。

为什么不能替代检索：

- Cross-Encoder 成本高，只能处理 TopN，不能扫全库。
- 如果 Dense/Sparse 没召回正确 chunk，Reranker 没法修复。
- 生产系统要先保证 Recall，再谈 rerank 排序。

Day 5 的最低要求是 MockReranker 必通。BGE-Reranker 可以作为可选真实模型路径，但不能因为模型下载或环境问题阻塞当天闭环。

## 7. 今日边界

### 7.1 为什么不做 Query Rewrite

Query Rewrite 会把原始 query 改写成更接近文档术语的表达，例如：

```text
直播卡顿 -> OTT 播放延迟高，检查 CDN 回源、首帧时间、缓冲率
```

它确实可能提高召回，但今天不能做，原因是：

- 它引入了新变量，无法判断提升来自 Hybrid 还是 Rewrite。
- Rewrite 通常依赖 LLM，会带来成本、延迟和不确定性。
- Rewrite 可能改变用户原意，尤其在高风险 TMS/养老场景不可随意扩写。

Day 5 的目标是比较 Dense、Sparse、Hybrid 和 Reranker，不是把 query 优化也混进来。

### 7.2 为什么不做 GraphRAG

GraphRAG 需要定义实体、关系、图构建、图检索和路径解释。它适合复杂多跳知识，但不是 Phase 0 Day 5 的目标。

今天不做 GraphRAG 的原因：

- 当前语料只有 30 个左右 chunk，知识图谱收益不明确。
- 图谱构建会引入额外 schema 和维护成本。
- Phase 0 当前目标是周六通关闭环，不是扩展复杂知识平台。

### 7.3 为什么不做 ReAct 深集成

Day 3 ReAct 控制流已经完成，Day 6 才负责集成。Day 5 不应该把 Hybrid 检索直接塞进 ReAct 状态机。

原因：

- Day 5 只验证检索策略，不验证 Agent 行为。
- ReAct 集成会引入工具调用、风险判断、HITL 等变量，污染检索对比。
- Day 3 的 unknown fallback、tool error Observation、HITL 边界必须在 Day 6 集成时保留。

Day 5 的输出应该是稳定的检索接口和最佳配置，供 Day 6 替换 `lookup_error_knowledge()`。

## 8. 风险与失败模式

| 风险 | 表现 | 处理 |
|---|---|---|
| 权重过拟合 | 某个 alpha 在 30 条 Query 上看似最好，但失败集中在某一领域 | 分领域看 TMS/OTT/养老，不只看总分 |
| Hybrid 退化 | Sparse 把精确词拉到错误 chunk，Top1 反而变差 | 记录退化 Query，必要时调整 alpha 或使用 RRF |
| Reranker 延迟 | TopN 过大导致平均延迟上升 | 限制候选池，例如 Top20 内重排 |
| 候选召回不足 | 正确 chunk 不在 Hybrid candidate_pool，Reranker 无法修复 | 先看 Recall@10/候选命中，再看 rerank |
| 分数尺度不一致 | Dense 0.45 和 BM25 7.3 无法直接相加 | 使用 normalize 或 RRF |
| 中文分词不稳定 | 错误码、版本号、百分比被拆碎或丢失 | 用正则保留英文、数字、下划线、版本号和单位 |
| No-answer 退化 | Hybrid 对无关 query 也强行召回 | 保留低置信阈值和 fallback 评估 |

## 9. 必须能回答的问题

### 为什么 Dense 不够？

Dense 擅长语义召回，但 TMS 场景大量证据是符号级精确匹配。错误码、设备型号、Android 版本、百分比阈值、容量单位和英文日志 token 不应只靠向量语义相似度判断。Dense 可能把 `证书校验` 拉向 EMQX 认证失败，也可能把 `CDN` 相关问题混到 OTA 下载超时与区域 CDN 命中率之间。

### BM25 为什么还有价值？

BM25 对短文本、专有名词、错误码、版本号和日志枚举值可靠。它的排序依据可解释：query 里的哪些词命中了哪个 chunk。对 TMS 运维场景来说，这种可解释精确命中是 Dense 的必要补充。

### Hybrid 权重怎么定？

用同一 30 条 Query 做 grid search。至少跑 `alpha=0.2/0.4/0.5/0.6/0.8`，比较 Recall@1、Recall@3、MRR、Context Precision、退化率和延迟。权重不能拍脑袋，也不能只看一个总分。

### RRF 为什么有用？

RRF 用排名融合，不依赖 Dense 和 BM25 的分数尺度一致。当两个检索器都把同一 chunk 排前时，它会自然得到更高融合分；当某一路分数异常偏大时，RRF 不容易被带偏。

### Reranker 为什么不能替代检索？

Cross-Encoder Reranker 更准但更慢，只适合 TopN 精排。它无法扫全库，也无法在候选池缺失正确 chunk 时创造正确答案。检索负责召回，Reranker 负责排序。

### 为什么今天不做 Query Rewrite？

Query Rewrite 会引入 LLM 改写质量、改写成本和语义漂移等新变量，污染 Dense vs Hybrid 的对比实验。今天只验证检索策略本身。

### 为什么今天不做 GraphRAG？

GraphRAG 是复杂知识图谱方向，不是 Phase 0 通关闭环所需。当前语料规模小，核心任务是证明 Hybrid 与 Reranker 是否比 Day 4 Dense baseline 更好。

## 10. 11:00 前自检

- [ ] 能写出 BM25 公式，并解释 `TF`、`IDF`、`k1`、`b`。
- [ ] 能用 6 个维度解释 Dense vs Sparse 的互补关系。
- [ ] 能写出 RRF、加权求和、线性插值三种融合公式。
- [ ] 能说明 Reranker 位置：Hybrid candidate_pool 后、final topK 前。
- [ ] 能解释为什么 Cross-Encoder 更准但更慢。
- [ ] 能说明 TMS 为什么需要 Sparse：错误码、设备型号、Android 版本、OTA、CDN、NTP。
- [ ] 能说明今日不做 Query Rewrite、GraphRAG、ReAct 深集成的原因。
- [ ] 能说清风险：权重过拟合、Hybrid 退化、Reranker 延迟、候选召回不足。
