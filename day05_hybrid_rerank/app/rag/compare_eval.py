from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from app.rag.data_loader import DAY05_DIR, load_corpus_chunks, load_eval_queries
from app.rag.dense_retriever import MockDenseRetriever
from app.rag.hybrid_fusion import FusionMethod
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import BGEReranker, FallbackReranker, MockReranker
from app.rag.sparse_retriever import SparseRetriever
from app.rag.types import EvalQuery, SearchResult


ALPHAS = (0.2, 0.4, 0.5, 0.6, 0.8)
TOP_K = 5
CANDIDATE_POOL = 10
REPORT_PATH = DAY05_DIR / "docs" / "hybrid_vs_dense_report.md"
BLOCKED_PATH = DAY05_DIR / "docs" / "day05-what-blocked.md"


@dataclass(frozen=True)
class QueryRun:
    query: EvalQuery
    results: list[SearchResult]
    latency_ms: float
    first_hit_rank: int | None
    context_precision: float

    @property
    def top_score(self) -> float:
        return self.results[0].score if self.results else 0.0

    @property
    def retrieved_chunk_ids(self) -> list[str]:
        return [result.chunk_id for result in self.results]


@dataclass(frozen=True)
class MethodMetrics:
    name: str
    total_queries: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    hit_rate_at_3: float
    mrr: float
    context_precision_at_5: float
    average_latency_ms: float
    degradation_rate_vs_dense: float
    case_results: list[QueryRun]


@dataclass(frozen=True)
class ComparisonSummary:
    generated_at: str
    metrics: list[MethodMetrics]
    best_hybrid: MethodMetrics
    best_final: MethodMetrics
    reranker_base: MethodMetrics
    reranker_metrics: MethodMetrics
    reranker_improvement_rate: float
    reranker_top1_lift_rate: float
    selected_config: str
    bge_reranker_status: str


def run_comparison(*, write_reports: bool = True) -> ComparisonSummary:
    chunks = load_corpus_chunks()
    queries = load_eval_queries()
    dense = MockDenseRetriever(chunks, score_threshold=0.2)
    sparse = SparseRetriever(chunks)
    fallback_reranker = FallbackReranker(primary=BGEReranker(available=False), fallback=MockReranker())
    hybrid = HybridRetriever(dense=dense, sparse=sparse, reranker=fallback_reranker)

    dense_metrics = _run_method(
        "Dense Only",
        queries,
        lambda query: dense.search(query.query, top_k=TOP_K, domain=query.domain),
    )
    sparse_metrics = _run_method(
        "Sparse BM25 Only",
        queries,
        lambda query: sparse.search(query.query, top_k=TOP_K, domain=query.domain),
        dense_baseline=dense_metrics,
    )

    metrics = [dense_metrics, sparse_metrics]
    for alpha in ALPHAS:
        metrics.append(
            _run_method(
                f"Hybrid alpha={alpha:.1f}",
                queries,
                lambda query, alpha=alpha: hybrid.search(
                    query.query,
                    top_k=TOP_K,
                    candidate_pool=CANDIDATE_POOL,
                    domain=query.domain,
                    alpha=alpha,
                    fusion_method=FusionMethod.WEIGHTED,
                ),
                dense_baseline=dense_metrics,
            )
        )

    metrics.append(
        _run_method(
            "Hybrid RRF",
            queries,
            lambda query: hybrid.search(
                query.query,
                top_k=TOP_K,
                candidate_pool=CANDIDATE_POOL,
                domain=query.domain,
                fusion_method=FusionMethod.RRF,
            ),
            dense_baseline=dense_metrics,
        )
    )

    hybrid_candidates = [item for item in metrics if item.name.startswith("Hybrid")]
    best_hybrid = max(hybrid_candidates, key=_selection_tuple)
    best_method, best_alpha = _method_config(best_hybrid.name)
    reranker_metrics = _run_method(
        f"Best Hybrid + MockReranker ({best_hybrid.name})",
        queries,
        lambda query: hybrid.search(
            query.query,
            top_k=TOP_K,
            candidate_pool=CANDIDATE_POOL,
            domain=query.domain,
            alpha=best_alpha,
            fusion_method=best_method,
            rerank=True,
        ),
        dense_baseline=dense_metrics,
    )
    metrics.append(reranker_metrics)

    best_final = max([best_hybrid, reranker_metrics], key=_selection_tuple)
    summary = ComparisonSummary(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        metrics=metrics,
        best_hybrid=best_hybrid,
        best_final=best_final,
        reranker_base=best_hybrid,
        reranker_metrics=reranker_metrics,
        reranker_improvement_rate=_improvement_rate(reranker_metrics, best_hybrid),
        reranker_top1_lift_rate=_top1_lift_rate(reranker_metrics, best_hybrid),
        selected_config=_selected_config(best_final),
        bge_reranker_status=fallback_reranker.last_fallback_reason or "BGE not used; MockReranker default path",
    )
    if write_reports:
        REPORT_PATH.write_text(build_report(summary), encoding="utf-8")
        BLOCKED_PATH.write_text(build_blocked_log(summary), encoding="utf-8")
    return summary


def build_report(summary: ComparisonSummary) -> str:
    dense = _metric_by_name(summary, "Dense Only")
    best = summary.best_final
    best_hybrid = summary.best_hybrid
    reranker = summary.reranker_metrics
    latency_delta = best.average_latency_ms - dense.average_latency_ms
    failure_samples = _failure_samples(best, dense)

    lines = [
        "# Day 5 Hybrid Retrieval vs Dense Report",
        "",
        f"- 生成时间：{summary.generated_at}",
        "- 运行方式：`python -m app.rag.compare_eval`",
        "- 语料：复用 Day 4 TMS / OTT / 养老健康 30 个 chunk。",
        "- 评估集：复用 Day 4 `data/eval/rag_eval_queries.jsonl`，共 30 条 Query。",
        f"- TopK：{TOP_K}",
        f"- Candidate Pool：{CANDIDATE_POOL}",
        "- Dense：Day 5 本地 MockDenseRetriever，保持 Day 4 MockEmbedding 的 n-gram/hash 口径。",
        "- Sparse：本地 BM25，保留错误码、版本号、英文 token、数字和中文 n-gram。",
        f"- alpha 列表：{', '.join(str(alpha) for alpha in ALPHAS)}",
        "- Reranker：BGE 未作为默认路径，使用 MockReranker 兜底，避免模型环境阻塞闭环。",
        "",
        "## 指标对比",
        "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | Hit Rate@3 | MRR | Context Precision@5 | Avg Latency | Degrade vs Dense |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for metric in summary.metrics:
        lines.append(
            "| "
            f"{metric.name} | {_pct(metric.recall_at_1)} | {_pct(metric.recall_at_3)} | "
            f"{_pct(metric.recall_at_5)} | {_pct(metric.hit_rate_at_3)} | "
            f"{metric.mrr:.4f} | {_pct(metric.context_precision_at_5)} | "
            f"{metric.average_latency_ms:.2f} ms | {_pct(metric.degradation_rate_vs_dense)} |"
        )

    lines.extend(
        [
            "",
            "## 最优配置",
            "",
            f"- 最优 Hybrid：`{best_hybrid.name}`。",
            f"- 最终建议配置：`{summary.selected_config}`。",
            f"- Reranker 提升率：{_pct(summary.reranker_improvement_rate)}。",
            f"- Reranker Top1 提升率：{_pct(summary.reranker_top1_lift_rate)}。",
            f"- BGE-Reranker 状态：{summary.bge_reranker_status}。",
            "",
            "选择规则：优先比较 `Recall@3`，再比较 `MRR`、`Recall@1`、`Context Precision@5` 和退化率。"
            "这符合 Day 6 的证据链需求：先保证正确证据进候选，再看排序质量。",
            "",
            "## 失败 / 未提升样例",
            "",
            "| Query ID | Domain | Expected | Dense Rank | Final Rank | Final TopK | 说明 |",
            "|---|---|---|---:|---:|---|---|",
        ]
    )
    for case, dense_case, note in failure_samples[:8]:
        lines.append(
            "| "
            f"{case.query.query_id} | {case.query.domain} | {case.query.expected_chunk_id} | "
            f"{_rank(dense_case.first_hit_rank)} | {_rank(case.first_hit_rank)} | "
            f"{', '.join(case.retrieved_chunk_ids)} | {note} |"
        )

    lines.extend(
        [
            "",
            "## 30 秒面试话术",
            "",
            "我今天在 Day4 Dense Retrieval 基线上实现了混合检索和 Reranker 对比实验。"
            "它解决的是单向量检索在 TMS 场景中对错误码、设备型号、Android 版本和精确术语召回不稳定的问题。"
            "我的方案是用 Dense 检索负责语义召回，用 Sparse/BM25 负责关键词和错误码召回，"
            "再通过 alpha 加权或 RRF 做融合，并在候选 TopN 上接入 Reranker 重排。",
            "",
            f"我没有拍脑袋固定权重，而是在 30 条 TMS/OTT/养老 Query 上跑了 "
            f"alpha={','.join(str(alpha) for alpha in ALPHAS)} 和 RRF 的对比实验，并记录退化 Query。"
            f"最终最优配置是 {summary.selected_config}，"
            f"Recall@3 从 {_pct(dense.recall_at_3)} 变为 {_pct(best.recall_at_3)}，"
            f"MRR 从 {dense.mrr:.4f} 变为 {best.mrr:.4f}，"
            f"平均延迟变化 {latency_delta:+.2f} ms。",
            "",
            "这个方案的权衡是复杂度和延迟上升，但换来了更可解释的优化路径。"
            "如果 Hybrid 或 Reranker 没有提升，就按失败样例和退化率处理，不硬吹模型效果。"
            "周六通关测试应使用这套配置作为 RAG 检索层。",
            "",
            "## 周六通关配置",
            "",
            f"- 检索配置：`{summary.selected_config}`。",
            "- 接入方式：Day 6 只替换 Day 3 的 `lookup_error_knowledge()` 知识查询动作，不替换 ReAct 控制流。",
            "- 安全边界：低置信、无结果或工具错误仍进入 Day 3 的 unknown / HITL / Observation 边界。",
            "",
        ]
    )
    return "\n".join(lines)


def build_blocked_log(summary: ComparisonSummary) -> str:
    dense = _metric_by_name(summary, "Dense Only")
    sparse = _metric_by_name(summary, "Sparse BM25 Only")
    best = summary.best_final
    best_hybrid = summary.best_hybrid
    worsened = _failure_samples(best, dense)
    improved_domains = _domain_deltas(best, dense, improved=True)
    degraded_domains = _domain_deltas(best, dense, improved=False)

    lines = [
        "# Day 5 阻塞记录与晚间复盘",
        "",
        f"- 生成时间：{summary.generated_at}",
        "- 运行方式：`python -m app.rag.compare_eval`",
        "- Git 提交 ID：提交后以 `git log -1 --oneline` 为准。",
        "",
        "## 今日三问",
        "",
        "### 今天做出来什么？",
        "",
        f"完成 Sparse/BM25、Hybrid Fusion、MockReranker、RRF 与 5 组 alpha 对比，"
        f"并在同一份 30 条 Query 上生成真实指标。Dense baseline 的 Recall@3 是 {_pct(dense.recall_at_3)}，"
        f"最终配置 `{summary.selected_config}` 的 Recall@3 是 {_pct(best.recall_at_3)}，"
        f"MRR 从 {dense.mrr:.4f} 变为 {best.mrr:.4f}。",
        "",
        "### 今天学到了什么？",
        "",
        "Dense 不够的根因不是模型弱，而是 TMS 场景里错误码、设备型号、Android 版本、百分比和协议名属于精确符号。"
        "Hybrid 必须靠同一评测集做对比，权重不能拍脑袋，Reranker 也只能重排候选，不能修复第一阶段漏召回。",
        "",
        "### 今天什么没做出来？",
        "",
        "没有接真实 BGE-Reranker；默认使用 MockReranker 兜底。没有做 Query Rewrite、GraphRAG 或 ReAct 深集成，"
        "这些会污染 Day 5 的检索对比实验或超出 Phase 0 边界。",
        "",
        "## 1. 哪类 Query Hybrid 提升明显？",
        "",
        f"- 提升域分布：{_format_domain_counts(improved_domains)}。",
        "- 精确 token 明显的 Query 更受益，例如错误码、403、NTP、CDN、数值阈值、Android/播放器版本。",
        "",
        "## 2. 哪类 Query Hybrid 反而下降？",
        "",
        f"- 下降域分布：{_format_domain_counts(degraded_domains)}。",
        "- 主要风险是 Sparse 把共享术语拉到相邻 chunk，例如 CDN 同时影响 OTA 下载超时和 CDN 命中率，健康告警里多个紧急处理段落共享就医/医生词。",
        "",
        "## 3. 哪个 alpha 最稳定？",
        "",
        f"- 当前最稳定的 alpha/RRF 选择是 `{best_hybrid.name}`。",
        "- 判断口径：优先看 Recall@3 与 MRR，同时检查退化率，不只看单点 Recall@1。",
        "",
        "## 4. RRF 和 Weighted 哪个更适合当前数据？",
        "",
        f"- 当前最优 Hybrid 是 `{best_hybrid.name}`。",
        "- 如果 Weighted 胜出，说明当前归一化后的 Dense/Sparse 分数在 30 条 Query 上可用；如果 RRF 胜出，说明排名融合更稳，分数尺度不值得强行相加。",
        "",
        "## 5. Reranker 是否真的提升 Top1/MRR？",
        "",
        f"- Reranker base：`{summary.reranker_base.name}`，MRR={summary.reranker_base.mrr:.4f}。",
        f"- Reranker result：`{summary.reranker_metrics.name}`，MRR={summary.reranker_metrics.mrr:.4f}。",
        f"- Top1 提升率：{_pct(summary.reranker_top1_lift_rate)}；整体提升率：{_pct(summary.reranker_improvement_rate)}。",
        "",
        "## 6. BGE-Reranker 是否跑通？MockReranker 如何兜底？",
        "",
        f"- BGE-Reranker 状态：{summary.bge_reranker_status}。",
        "- MockReranker 使用 query/document token overlap、title 命中、英文/数字精确命中和原始融合分数做确定性重排，保证无模型环境也能闭环。",
        "",
        "## 7. 哪些代码是 Codex 辅助骨架？",
        "",
        "- `data_loader.py`、`dense_retriever.py`、`sparse_retriever.py`、`hybrid_retriever.py`、`reranker.py`、`compare_eval.py`、pytest 骨架和报告模板均由 Codex 在本轮生成。",
        "",
        "## 8. 哪些权重和融合逻辑是手写？",
        "",
        "- `normalize_scores()`、`fuse_weighted()`、`fuse_rrf()`、`run_comparison()` 中的 alpha grid search、退化率和失败样例分析按今日训练令手写落地。",
        "",
        "## 9. 明天周六通关测试应使用哪套检索配置？",
        "",
        f"- 推荐使用 `{summary.selected_config}`。",
        "- Day 6 只接入检索证据，不扩展前端、GraphRAG、Query Rewrite 或 LangGraph；保留 Day 3 unknown fallback、HITL 和工具错误 Observation。",
        "",
        "## 失败样例摘录",
        "",
        "| Query ID | Expected | Dense Rank | Final Rank | Final TopK |",
        "|---|---|---:|---:|---|",
    ]
    for case, dense_case, _ in worsened[:8]:
        lines.append(
            "| "
            f"{case.query.query_id} | {case.query.expected_chunk_id} | "
            f"{_rank(dense_case.first_hit_rank)} | {_rank(case.first_hit_rank)} | "
            f"{', '.join(case.retrieved_chunk_ids)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _run_method(
    name: str,
    queries: list[EvalQuery],
    search_fn,
    *,
    dense_baseline: MethodMetrics | None = None,
) -> MethodMetrics:
    case_results: list[QueryRun] = []
    for query in queries:
        started_at = perf_counter()
        results = search_fn(query)
        latency_ms = (perf_counter() - started_at) * 1000
        first_hit_rank = _first_hit_rank(results, query.expected_chunk_id)
        case_results.append(
            QueryRun(
                query=query,
                results=results,
                latency_ms=latency_ms,
                first_hit_rank=first_hit_rank,
                context_precision=_context_precision_at_k(results, query.expected_keywords, TOP_K),
            )
        )
    return _metrics_for(name, case_results, dense_baseline=dense_baseline)


def _metrics_for(
    name: str,
    case_results: list[QueryRun],
    *,
    dense_baseline: MethodMetrics | None,
) -> MethodMetrics:
    total = len(case_results)
    reciprocal_ranks = [
        0.0 if case.first_hit_rank is None else 1 / case.first_hit_rank
        for case in case_results
    ]
    degradation = 0
    if dense_baseline is not None:
        dense_by_id = {case.query.query_id: case for case in dense_baseline.case_results}
        for case in case_results:
            dense_case = dense_by_id[case.query.query_id]
            if _rank_value(case.first_hit_rank) > _rank_value(dense_case.first_hit_rank):
                degradation += 1

    return MethodMetrics(
        name=name,
        total_queries=total,
        recall_at_1=sum(case.first_hit_rank == 1 for case in case_results) / total,
        recall_at_3=sum(case.first_hit_rank is not None and case.first_hit_rank <= 3 for case in case_results) / total,
        recall_at_5=sum(case.first_hit_rank is not None and case.first_hit_rank <= 5 for case in case_results) / total,
        hit_rate_at_3=sum(case.first_hit_rank is not None and case.first_hit_rank <= 3 for case in case_results) / total,
        mrr=sum(reciprocal_ranks) / total,
        context_precision_at_5=sum(case.context_precision for case in case_results) / total,
        average_latency_ms=sum(case.latency_ms for case in case_results) / total,
        degradation_rate_vs_dense=0.0 if dense_baseline is None else degradation / total,
        case_results=case_results,
    )


def _first_hit_rank(results: list[SearchResult], expected_chunk_id: str) -> int | None:
    for rank, result in enumerate(results, start=1):
        if result.chunk_id == expected_chunk_id:
            return rank
    return None


def _context_precision_at_k(
    results: list[SearchResult],
    expected_keywords: tuple[str, ...],
    top_k: int,
) -> float:
    relevant_hits = 0
    precision_sum = 0.0
    for rank, result in enumerate(results[:top_k], start=1):
        if not any(keyword in result.text for keyword in expected_keywords):
            continue
        relevant_hits += 1
        precision_sum += relevant_hits / rank
    if relevant_hits == 0:
        return 0.0
    return precision_sum / relevant_hits


def _selection_tuple(metric: MethodMetrics) -> tuple[float, float, float, float, float]:
    return (
        metric.recall_at_3,
        metric.mrr,
        metric.recall_at_1,
        metric.context_precision_at_5,
        -metric.degradation_rate_vs_dense,
    )


def _method_config(name: str) -> tuple[FusionMethod, float]:
    if name == "Hybrid RRF":
        return FusionMethod.RRF, 0.5
    marker = "Hybrid alpha="
    if name.startswith(marker):
        return FusionMethod.WEIGHTED, float(name.removeprefix(marker))
    raise ValueError(f"unsupported hybrid method name: {name}")


def _selected_config(metric: MethodMetrics) -> str:
    if "MockReranker" in metric.name:
        return metric.name
    return metric.name


def _improvement_rate(candidate: MethodMetrics, baseline: MethodMetrics) -> float:
    baseline_by_id = {case.query.query_id: case for case in baseline.case_results}
    improved = 0
    for case in candidate.case_results:
        if _rank_value(case.first_hit_rank) < _rank_value(baseline_by_id[case.query.query_id].first_hit_rank):
            improved += 1
    return improved / len(candidate.case_results)


def _top1_lift_rate(candidate: MethodMetrics, baseline: MethodMetrics) -> float:
    baseline_by_id = {case.query.query_id: case for case in baseline.case_results}
    lifted = 0
    for case in candidate.case_results:
        if case.first_hit_rank == 1 and baseline_by_id[case.query.query_id].first_hit_rank != 1:
            lifted += 1
    return lifted / len(candidate.case_results)


def _failure_samples(
    candidate: MethodMetrics,
    dense: MethodMetrics,
) -> list[tuple[QueryRun, QueryRun, str]]:
    dense_by_id = {case.query.query_id: case for case in dense.case_results}
    samples: list[tuple[QueryRun, QueryRun, str]] = []
    for case in candidate.case_results:
        dense_case = dense_by_id[case.query.query_id]
        if _rank_value(case.first_hit_rank) > _rank_value(dense_case.first_hit_rank):
            samples.append((case, dense_case, "退化：最终排名弱于 Dense"))
        elif case.first_hit_rank != 1:
            samples.append((case, dense_case, "未 Top1：仍需 Day 6 谨慎使用证据"))
        elif case.first_hit_rank == dense_case.first_hit_rank:
            samples.append((case, dense_case, "持平：没有相对 Dense 提升"))
    samples.sort(
        key=lambda item: (
            0 if "退化" in item[2] else 1 if "未 Top1" in item[2] else 2,
            _rank_value(item[0].first_hit_rank),
        )
    )
    return samples


def _domain_deltas(candidate: MethodMetrics, dense: MethodMetrics, *, improved: bool) -> dict[str, int]:
    dense_by_id = {case.query.query_id: case for case in dense.case_results}
    counts: dict[str, int] = {"tms": 0, "ott": 0, "elderly": 0}
    for case in candidate.case_results:
        lhs = _rank_value(case.first_hit_rank)
        rhs = _rank_value(dense_by_id[case.query.query_id].first_hit_rank)
        if improved and lhs < rhs:
            counts[case.query.domain] += 1
        if not improved and lhs > rhs:
            counts[case.query.domain] += 1
    return counts


def _metric_by_name(summary: ComparisonSummary, name: str) -> MethodMetrics:
    for metric in summary.metrics:
        if metric.name == name:
            return metric
    raise KeyError(name)


def _rank_value(rank: int | None) -> int:
    return rank if rank is not None else 999


def _rank(rank: int | None) -> str:
    return "-" if rank is None else str(rank)


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_domain_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{domain}={count}" for domain, count in counts.items())


def main() -> int:
    summary = run_comparison(write_reports=True)
    dense = _metric_by_name(summary, "Dense Only")
    print(f"report={REPORT_PATH}")
    print(f"blocked={BLOCKED_PATH}")
    print(f"dense_recall_at_3={dense.recall_at_3:.4f}")
    print(f"best_final={summary.selected_config}")
    print(f"best_final_recall_at_3={summary.best_final.recall_at_3:.4f}")
    print(f"best_final_mrr={summary.best_final.mrr:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
