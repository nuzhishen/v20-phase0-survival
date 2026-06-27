from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys


# 允许从仓库根目录或 day04_rag_pipeline 目录直接运行本脚本。
DAY04_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DAY04_DIR))

from app.documents import load_corpus_chunks
from app.rag_pipeline import build_in_memory_pipeline, evaluate_retriever, load_eval_queries
from app.schemas import EvalMetrics


DEFAULT_REPORT_PATH = DAY04_DIR / "docs" / "rag_baseline_report.md"


def _percent(value: float) -> str:
    """把 0~1 的指标格式化成百分比，报告里更直观。"""

    return f"{value * 100:.2f}%"


def _metric_row(name: str, value: str, baseline: str, note: str) -> str:
    """生成 Markdown 表格的一行，避免手写报告时数字和脚本脱节。"""

    return f"| {name} | {value} | {baseline} | {note} |"


def build_report(metrics: EvalMetrics) -> str:
    """根据真实评测结果生成 Day 4 基线报告。

    报告只写脚本实际算出来的数据，不手填“看起来好看”的数字。
    这是 RAG 工程里很重要的习惯：先把检索结果量化，再讨论怎么优化。
    """

    chunks = load_corpus_chunks()
    domain_counts = {
        "tms": sum(chunk.domain == "tms" for chunk in chunks),
        "ott": sum(chunk.domain == "ott" for chunk in chunks),
        "elderly": sum(chunk.domain == "elderly" for chunk in chunks),
    }
    failed_cases = [
        case
        for case in metrics.case_results
        if case.first_hit_rank != 1 or case.top_score < 0.35
    ]

    lines = [
        "# Day 4 RAG Baseline Report",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 运行方式：`python run_day04_eval.py`",
        "- 默认链路：`MockEmbedding -> InMemoryVectorStore -> Retriever -> 8 metrics`",
        "- 真实 Qdrant/BGE：通过 `run_day04_qdrant_smoke.py` 单独验证，避免单元测试依赖外部服务。",
        "",
        "## 语料与评估集",
        "",
        f"- TMS chunk 数：{domain_counts['tms']}",
        f"- OTT chunk 数：{domain_counts['ott']}",
        f"- 养老健康 chunk 数：{domain_counts['elderly']}",
        f"- 测试 Query 数：{metrics.total_queries}",
        "- 每条 Query 都包含 `expected_chunk_id`、`expected_keywords`、`ground_truth_context`、`ground_truth_answer`。",
        "",
        "## 8 指标结果",
        "",
        "| 指标 | Day 4 实测 | Day 4 基线 | 说明 |",
        "|---|---:|---:|---|",
        _metric_row("Recall@1", _percent(metrics.recall_at_1), ">= 40.00%", "Top1 是否命中预期 chunk"),
        _metric_row("Recall@3", _percent(metrics.recall_at_3), ">= 60.00%", "Top3 是否命中预期 chunk"),
        _metric_row("Recall@5", _percent(metrics.recall_at_5), ">= 50.00%", "Day 4 最核心检索基线"),
        _metric_row("MRR", f"{metrics.mrr:.4f}", ">= 0.6000", "首个正确 chunk 越靠前越好"),
        _metric_row(
            "Context Precision@5",
            _percent(metrics.context_precision_at_5),
            ">= 60.00%",
            "按 AP@K 计算，相关证据越靠前越高",
        ),
        _metric_row("No-answer/Fallback", _percent(metrics.no_answer_fallback_accuracy), ">= 80.00%", "无关 query 应为空或低置信"),
        _metric_row("低分率", _percent(metrics.low_score_rate), "< 20.00%", "Top score < 0.35 的比例"),
        _metric_row("平均检索延迟", f"{metrics.average_latency_ms:.2f} ms", "< 200 ms", "本地 Mock + InMemory 基线"),
        "",
        "## 未 Top1 命中的 Query",
        "",
    ]

    if failed_cases:
        lines.extend(
            [
                "| Query ID | 领域 | 预期 chunk | 实际 Top-K | 首中排名 | Top score |",
                "|---|---|---|---|---:|---:|",
            ]
        )
        for case in failed_cases:
            lines.append(
                "| "
                f"{case.query_id} | {case.domain} | {case.expected_chunk_id} | "
                f"{', '.join(case.retrieved_chunk_ids)} | {case.first_hit_rank or '-'} | "
                f"{case.top_score:.4f} |"
            )
    else:
        lines.append("- 全部 Query 的预期 chunk 均在 Top1，当前没有未命中样例。")

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- Day 4 已完成 Dense Retrieval 基线，但这不是最终生产检索方案。",
            "- MockEmbedding 只用于稳定测试，不声称等价于真实 BGE 语义质量。",
            "- 纯 Dense 仍可能遇到语义鸿沟，Day 5 应用混合检索和 reranker 做对比实验。",
            "- Qdrant 连接、HNSW 参数和 Payload 过滤已在源码中实现；API Key 通过环境变量读取，不写入仓库。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Phase 0 Day 4 RAG 评估报告")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown 报告输出路径",
    )
    args = parser.parse_args()

    retriever, _ = build_in_memory_pipeline(score_threshold=0.2)
    metrics = evaluate_retriever(retriever, load_eval_queries(), top_k=5)
    report = build_report(metrics)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(report, encoding="utf-8")

    print(f"report={args.report_path}")
    print(f"recall_at_5={metrics.recall_at_5:.4f}")
    print(f"context_precision_at_5={metrics.context_precision_at_5:.4f}")
    print(f"no_answer_fallback_accuracy={metrics.no_answer_fallback_accuracy:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
