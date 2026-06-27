from __future__ import annotations

import json
from pathlib import Path

from app.documents import load_corpus_chunks
from app.embedding import EmbeddingProvider, MockEmbedding
from app.retriever import Retriever
from app.schemas import EvalCaseResult, EvalMetrics, EvalQuery, RetrievalResult
from app.vector_store import InMemoryVectorStore, VectorStore


EVAL_PATH = Path(__file__).resolve().parents[1] / "data" / "eval" / "rag_eval_queries.jsonl"


def build_in_memory_pipeline(
    *,
    embedder: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    score_threshold: float = 0.2,
) -> tuple[Retriever, list[str]]:
    """构建可测试的本地 RAG Pipeline。

    默认使用 MockEmbedding + InMemoryVectorStore，不依赖 Qdrant 和 BGE。
    返回值中的 chunk_id 列表用于测试确认语料完整性。
    """

    actual_embedder = embedder or MockEmbedding(vector_size=256)
    actual_store = vector_store or InMemoryVectorStore()
    chunks = load_corpus_chunks()
    embeddings = actual_embedder.embed_texts([chunk.text for chunk in chunks])
    actual_store.create_collection(actual_embedder.vector_size)
    actual_store.upsert_chunks(chunks, embeddings)
    retriever = Retriever(
        embedder=actual_embedder,
        vector_store=actual_store,
        score_threshold=score_threshold,
    )
    return retriever, [chunk.chunk_id for chunk in chunks]


def load_eval_queries(path: Path | None = None) -> list[EvalQuery]:
    eval_path = path or EVAL_PATH
    queries: list[EvalQuery] = []
    for line_number, line in enumerate(eval_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            queries.append(EvalQuery.model_validate(json.loads(line)))
        except Exception as error:
            raise ValueError(f"Invalid eval query at line {line_number}: {error}") from error
    return queries


def evaluate_retriever(
    retriever: Retriever,
    queries: list[EvalQuery],
    *,
    top_k: int = 5,
    low_score_threshold: float = 0.35,
) -> EvalMetrics:
    """计算 Day 4 要求的核心评估指标。

    Context Precision 使用 `expected_keywords` 做弱人工标注，并按排名计算 AP@K：
    如果相关证据排第 1 位，精度接近 1；如果排第 5 位，精度会明显下降。
    这比简单的 `相关条数 / top_k` 更接近 RAGAS 对“上下文排序质量”的定义。
    Day 4 没有真实生成，因此不计算 Faithfulness 和 Answer Relevancy。
    """

    case_results: list[EvalCaseResult] = []
    recall_1 = 0
    recall_3 = 0
    recall_5 = 0
    reciprocal_ranks: list[float] = []
    precisions: list[float] = []
    low_score_count = 0
    total_latency = 0.0

    for query in queries:
        response = retriever.retrieve(query.query, top_k=top_k, domain=query.domain)
        retrieved_ids = [result.chunk_id for result in response.results]
        first_hit_rank: int | None = None
        for index, chunk_id in enumerate(retrieved_ids, start=1):
            if chunk_id == query.expected_chunk_id:
                first_hit_rank = index
                break

        if first_hit_rank == 1:
            recall_1 += 1
        if first_hit_rank is not None and first_hit_rank <= 3:
            recall_3 += 1
        if first_hit_rank is not None and first_hit_rank <= 5:
            recall_5 += 1
            reciprocal_ranks.append(1 / first_hit_rank)
        else:
            reciprocal_ranks.append(0.0)

        precision = _context_precision_at_k(
            response.results,
            expected_keywords=query.expected_keywords,
            top_k=top_k,
        )
        precisions.append(precision)
        top_score = response.results[0].score if response.results else 0.0
        if top_score < low_score_threshold:
            low_score_count += 1
        total_latency += response.latency_ms
        case_results.append(
            EvalCaseResult(
                query_id=query.query_id,
                domain=query.domain,
                expected_chunk_id=query.expected_chunk_id,
                retrieved_chunk_ids=retrieved_ids,
                first_hit_rank=first_hit_rank,
                top_score=top_score,
                latency_ms=response.latency_ms,
                context_precision=precision,
            )
        )

    total = len(queries)
    if total == 0:
        raise ValueError("queries must not be empty")
    return EvalMetrics(
        total_queries=total,
        recall_at_1=recall_1 / total,
        recall_at_3=recall_3 / total,
        recall_at_5=recall_5 / total,
        mrr=sum(reciprocal_ranks) / total,
        context_precision_at_5=sum(precisions) / total,
        low_score_rate=low_score_count / total,
        average_latency_ms=total_latency / total,
        no_answer_fallback_accuracy=measure_no_answer_accuracy(retriever),
        case_results=case_results,
    )


def measure_no_answer_accuracy(retriever: Retriever) -> float:
    """用固定无关 Query 检查 no-answer/fallback 能力。"""

    negative_queries = [
        ("weather_001", "今天上海天气怎么样？", "tms"),
        ("travel_001", "帮我订一张去北京的机票", "ott"),
        ("finance_001", "现在买哪只股票收益最高？", "elderly"),
    ]
    correct = 0
    for _, query, domain in negative_queries:
        response = retriever.retrieve(query, top_k=5, domain=domain)  # type: ignore[arg-type]
        if response.low_confidence:
            correct += 1
    return correct / len(negative_queries)


def _context_precision_at_k(
    results: list[RetrievalResult],
    *,
    expected_keywords: list[str],
    top_k: int,
) -> float:
    """按 AP@K 计算 Context Precision。

    初学者可以把它理解为“相关证据越靠前越好”：
    - 第 1 条就是相关证据：precision 很高。
    - 第 5 条才是相关证据：precision 会被惩罚。
    - 没有相关证据：precision 为 0。
    """

    if top_k <= 0:
        return 0.0

    relevant_hits = 0
    precision_sum = 0.0
    for rank, result in enumerate(results[:top_k], start=1):
        is_relevant = any(keyword in result.text for keyword in expected_keywords)
        if not is_relevant:
            continue
        relevant_hits += 1
        precision_sum += relevant_hits / rank

    if relevant_hits == 0:
        return 0.0
    return precision_sum / relevant_hits
