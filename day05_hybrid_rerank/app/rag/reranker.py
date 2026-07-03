from __future__ import annotations

from collections import Counter
from typing import Protocol

from app.rag.sparse_retriever import tokenize_for_sparse
from app.rag.types import SearchResult


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 3,
        expected_keywords: tuple[str, ...] = (),
    ) -> list[SearchResult]:
        ...


class MockReranker:
    """Deterministic reranker that uses query/document overlap only by default."""

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 3,
        expected_keywords: tuple[str, ...] = (),
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not candidates:
            return []

        query_tokens = Counter(tokenize_for_sparse(query))
        keyword_tokens = Counter(
            token
            for keyword in expected_keywords
            for token in tokenize_for_sparse(keyword)
        )
        reranked: list[SearchResult] = []
        for rank, candidate in enumerate(candidates, start=1):
            text = f"{candidate.title}\n{candidate.text}\n{' '.join(candidate.metadata.values())}"
            doc_tokens = Counter(tokenize_for_sparse(text))
            overlap = sum(min(count, doc_tokens.get(token, 0)) for token, count in query_tokens.items())
            keyword_overlap = sum(
                min(count, doc_tokens.get(token, 0))
                for token, count in keyword_tokens.items()
            )
            title_overlap = sum(
                1
                for token in query_tokens
                if token in tokenize_for_sparse(candidate.title)
            )
            exact_ascii_hits = sum(
                1
                for token in query_tokens
                if token.isascii() and token in text.lower()
            )
            rerank_score = (
                overlap
                + 1.5 * title_overlap
                + 2.0 * exact_ascii_hits
                + 0.5 * keyword_overlap
                + 0.05 * candidate.score
                + 0.001 / rank
            )
            method_scores = dict(candidate.method_scores)
            method_scores["rerank_score"] = rerank_score
            reranked.append(candidate.with_score(rerank_score, method_scores=method_scores))

        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked[:top_k]


class BGEReranker:
    """Optional real reranker placeholder.

    Day 5 does not require a live model. The class is intentionally explicit:
    if the model path is not configured, callers must fall back to MockReranker.
    """

    def __init__(self, available: bool = False) -> None:
        self.available = available

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 3,
        expected_keywords: tuple[str, ...] = (),
    ) -> list[SearchResult]:
        if not self.available:
            raise RuntimeError("BGE reranker is not configured in Day 5 default path")
        return MockReranker().rerank(
            query,
            candidates,
            top_k=top_k,
            expected_keywords=expected_keywords,
        )


class FallbackReranker:
    def __init__(self, primary: Reranker | None = None, fallback: Reranker | None = None) -> None:
        self.primary = primary
        self.fallback = fallback or MockReranker()
        self.last_fallback_reason: str | None = None

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 3,
        expected_keywords: tuple[str, ...] = (),
    ) -> list[SearchResult]:
        if self.primary is not None:
            try:
                self.last_fallback_reason = None
                return self.primary.rerank(
                    query,
                    candidates,
                    top_k=top_k,
                    expected_keywords=expected_keywords,
                )
            except Exception as error:  # noqa: BLE001
                self.last_fallback_reason = f"{type(error).__name__}:{error}"
        return self.fallback.rerank(
            query,
            candidates,
            top_k=top_k,
            expected_keywords=expected_keywords,
        )
