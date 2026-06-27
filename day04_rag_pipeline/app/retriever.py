from __future__ import annotations

from time import perf_counter

from app.embedding import EmbeddingProvider
from app.schemas import Domain, RetrievalResponse
from app.vector_store import VectorStore


class Retriever:
    """查询 -> 向量 -> top_k 检索的最小 Pipeline。

    Retriever 不负责生成答案，只负责返回证据、耗时和低置信标志。
    这正是 Day 4 的边界：先证明检索可评估，再把结果交给后续 ReAct/LLM。
    """

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        fallback_store: VectorStore | None = None,
        score_threshold: float = 0.5,
        confidence_threshold: float = 0.35,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.fallback_store = fallback_store
        self.score_threshold = score_threshold
        self.confidence_threshold = confidence_threshold

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        domain: Domain | None = None,
    ) -> RetrievalResponse:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        started_at = perf_counter()
        query_vector = self.embedder.embed_query(query)
        fallback_reason: str | None = None
        try:
            results = self.vector_store.search(
                query_vector,
                top_k=top_k,
                domain_filter=domain,
                score_threshold=self.score_threshold,
            )
        except Exception as error:
            if self.fallback_store is None:
                raise
            fallback_reason = f"PRIMARY_VECTOR_STORE_FAILED:{type(error).__name__}"
            results = self.fallback_store.search(
                query_vector,
                top_k=top_k,
                domain_filter=domain,
                score_threshold=self.score_threshold,
            )

        latency_ms = (perf_counter() - started_at) * 1000
        top_score = results[0].score if results else 0.0
        low_confidence = len(results) == 0 or top_score < self.confidence_threshold
        if low_confidence and fallback_reason is None:
            if len(results) == 0:
                fallback_reason = "NO_RELEVANT_CONTEXT"
            else:
                fallback_reason = "LOW_TOP_SCORE"

        return RetrievalResponse(
            query=query,
            domain=domain,
            top_k=top_k,
            latency_ms=latency_ms,
            low_confidence=low_confidence,
            fallback_reason=fallback_reason,
            results=results,
        )
