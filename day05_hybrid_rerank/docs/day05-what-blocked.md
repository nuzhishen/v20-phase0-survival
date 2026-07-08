# Day 5 阻塞记录与晚间复盘

- 生成时间：2026-07-07T21:53:03
- 运行方式：`python -m app.rag.compare_eval`
- Git 提交 ID：提交后以 `git log -1 --oneline` 为准。

## 今日三问

### 今天做出来什么？

完成 Sparse/BM25、Hybrid Fusion、MockReranker、RRF 与 5 组 alpha 对比，并在同一份 30 条 Query 上生成真实指标。Dense baseline 的 Recall@3 是 90.00%，最终配置 `Best Hybrid + MockReranker (Hybrid alpha=0.6)` 的 Recall@3 是 100.00%，MRR 从 0.8678 变为 1.0000。

### 今天学到了什么？

Dense 不够的根因不是模型弱，而是 TMS 场景里错误码、设备型号、Android 版本、百分比和协议名属于精确符号。Hybrid 必须靠同一评测集做对比，权重不能拍脑袋，Reranker 也只能重排候选，不能修复第一阶段漏召回。

### 今天什么没做出来？

没有接真实 BGE-Reranker；默认使用 MockReranker 兜底。没有做 Query Rewrite、GraphRAG 或 ReAct 深集成，这些会污染 Day 5 的检索对比实验或超出 Phase 0 边界。

## 1. 哪类 Query Hybrid 提升明显？

- 提升域分布：tms=3, ott=1, elderly=2。
- 精确 token 明显的 Query 更受益，例如错误码、403、NTP、CDN、数值阈值、Android/播放器版本。

## 2. 哪类 Query Hybrid 反而下降？

- 下降域分布：tms=0, ott=0, elderly=0。
- 主要风险是 Sparse 把共享术语拉到相邻 chunk，例如 CDN 同时影响 OTA 下载超时和 CDN 命中率，健康告警里多个紧急处理段落共享就医/医生词。

## 3. 哪个 alpha 最稳定？

- 当前最稳定的 alpha/RRF 选择是 `Hybrid alpha=0.6`。
- 判断口径：优先看 Recall@3 与 MRR，同时检查退化率，不只看单点 Recall@1。

## 4. RRF 和 Weighted 哪个更适合当前数据？

- 当前最优 Hybrid 是 `Hybrid alpha=0.6`。
- 如果 Weighted 胜出，说明当前归一化后的 Dense/Sparse 分数在 30 条 Query 上可用；如果 RRF 胜出，说明排名融合更稳，分数尺度不值得强行相加。

## 5. Reranker 是否真的提升 Top1/MRR？

- Reranker base：`Hybrid alpha=0.6`，MRR=0.9833。
- Reranker result：`Best Hybrid + MockReranker (Hybrid alpha=0.6)`，MRR=1.0000。
- Top1 提升率：3.33%；整体提升率：3.33%。

## 6. BGE-Reranker 是否跑通？MockReranker 如何兜底？

- BGE-Reranker 状态：RuntimeError:BGE reranker is not configured in Day 5 default path。
- MockReranker 使用 query/document token overlap、title 命中、英文/数字精确命中和原始融合分数做确定性重排，保证无模型环境也能闭环。

## 7. 哪些代码是 Codex 辅助骨架？

- `data_loader.py`、`dense_retriever.py`、`sparse_retriever.py`、`hybrid_retriever.py`、`reranker.py`、`compare_eval.py`、pytest 骨架和报告模板均由 Codex 在本轮生成。

## 8. 哪些权重和融合逻辑是手写？

- `normalize_scores()`、`fuse_weighted()`、`fuse_rrf()`、`run_comparison()` 中的 alpha grid search、退化率和失败样例分析按今日训练令手写落地。

## 9. 明天周六通关测试应使用哪套检索配置？

- 推荐使用 `Best Hybrid + MockReranker (Hybrid alpha=0.6)`。
- Day 6 只接入检索证据，不扩展前端、GraphRAG、Query Rewrite 或 LangGraph；保留 Day 3 unknown fallback、HITL 和工具错误 Observation。

## 失败样例摘录

| Query ID | Expected | Dense Rank | Final Rank | Final TopK |
|---|---|---:|---:|---|
| tms_001 | tms_e1001 | 1 | 1 | tms_e1001, tms_e1010, tms_e1007, tms_e1004, tms_e1002 |
| tms_003 | tms_e1003 | 1 | 1 | tms_e1003, tms_e1004, tms_e1008, tms_e1002, tms_e1007 |
| tms_005 | tms_e1005 | 1 | 1 | tms_e1005, tms_e1003, tms_e1006, tms_e1001, tms_e1007 |
| tms_006 | tms_e1006 | 1 | 1 | tms_e1006, tms_e1004, tms_e1001, tms_e1007, tms_e1003 |
| tms_007 | tms_e1007 | 1 | 1 | tms_e1007, tms_e1002, tms_e1004, tms_e1010, tms_e1008 |
| tms_008 | tms_e1008 | 1 | 1 | tms_e1008, tms_e1004, tms_e1002, tms_e1007, tms_e1009 |
| tms_009 | tms_e1009 | 1 | 1 | tms_e1009, tms_e1002, tms_e1004, tms_e1003, tms_e1006 |
| ott_001 | ott_q001 | 1 | 1 | ott_q001, ott_q005, ott_q010, ott_q007, ott_q002 |
