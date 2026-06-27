from __future__ import annotations

from abc import ABC, abstractmethod
import math

from app.schemas import ChunkPayload, Domain, RetrievalResult


class VectorStore(ABC):
    """向量存储抽象。

    Qdrant 和 InMemory 都实现同一组方法，Retriever 不关心底层是外部服务
    还是本地列表。这是 Day 4 稳定性兜底的关键。
    """

    @abstractmethod
    def create_collection(self, vector_size: int) -> None:
        """初始化 collection。"""

    @abstractmethod
    def upsert_chunks(
        self,
        chunks: list[ChunkPayload],
        embeddings: list[list[float]],
    ) -> None:
        """写入 chunk 与向量。"""

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        domain_filter: Domain | None = None,
        score_threshold: float = 0.5,
    ) -> list[RetrievalResult]:
        """检索 Top-K。"""


class InMemoryVectorStore(VectorStore):
    """纯内存向量库。

    它用于单元测试和 Qdrant 故障降级，不依赖任何外部服务。
    算法是暴力 KNN，数据量只有几十个 chunk 时足够，而且结果确定。
    """

    def __init__(self) -> None:
        self.vector_size: int | None = None
        self._items: list[tuple[ChunkPayload, list[float]]] = []

    def create_collection(self, vector_size: int) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive")
        self.vector_size = vector_size
        self._items.clear()

    def upsert_chunks(
        self,
        chunks: list[ChunkPayload],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        for embedding in embeddings:
            self._validate_vector(embedding)

        # chunk_id 是稳定主键；重复 upsert 时先删旧值，保证幂等。
        incoming_ids = {chunk.chunk_id for chunk in chunks}
        self._items = [
            (chunk, vector)
            for chunk, vector in self._items
            if chunk.chunk_id not in incoming_ids
        ]
        self._items.extend(zip(chunks, embeddings, strict=True))

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        domain_filter: Domain | None = None,
        score_threshold: float = 0.5,
    ) -> list[RetrievalResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self._validate_vector(query_vector)

        scored: list[RetrievalResult] = []
        for chunk, vector in self._items:
            if domain_filter is not None and chunk.domain != domain_filter:
                continue
            score = _cosine_similarity(query_vector, vector)
            if score < score_threshold:
                continue
            scored.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    domain=chunk.domain,
                    source=chunk.source,
                    title=chunk.title,
                    text=chunk.text,
                    score=score,
                    metadata=chunk.metadata,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _validate_vector(self, vector: list[float]) -> None:
        if self.vector_size is None:
            raise RuntimeError("collection has not been created")
        if len(vector) != self.vector_size:
            raise ValueError(
                f"vector size mismatch: expected {self.vector_size}, got {len(vector)}"
            )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    # Qdrant COSINE 返回通常在 0~1 附近；这里把负数压到 0，便于阈值判断。
    return max(dot / (left_norm * right_norm), 0.0)

