from __future__ import annotations

from collections import Counter
import math
import re

from app.rag.data_loader import index_text_for_chunk
from app.rag.types import Chunk, Domain, SearchResult


_ASCII_OR_NUMBER = re.compile(
    r"(?i)(?:[a-z]+[a-z0-9_-]*[a-z0-9]|[a-z]+|\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?%?(?:mb|gb|ms|小时|分钟|摄氏度)?)"
)
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def tokenize_for_sparse(text: str) -> list[str]:
    """Tokenize Chinese operations text while preserving codes and versions."""

    lowered = text.lower()
    tokens: list[str] = []
    tokens.extend(match.group(0) for match in _ASCII_OR_NUMBER.finditer(lowered))

    for cjk_match in _CJK.finditer(lowered):
        segment = cjk_match.group(0)
        if len(segment) == 1:
            tokens.append(segment)
            continue
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        tokens.extend(segment[index : index + 3] for index in range(len(segment) - 2))
        if len(segment) <= 6:
            tokens.append(segment)

    return [token for token in tokens if token.strip()]


class SparseRetriever:
    """Small self-contained BM25 retriever for Day 5 comparison experiments."""

    def __init__(
        self,
        chunks: list[Chunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 < 0:
            raise ValueError("k1 must be non-negative")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._doc_tokens = [tokenize_for_sparse(index_text_for_chunk(chunk)) for chunk in chunks]
        self._term_freqs = [Counter(tokens) for tokens in self._doc_tokens]
        self._doc_lengths = [len(tokens) for tokens in self._doc_tokens]
        self._avgdl = (
            sum(self._doc_lengths) / len(self._doc_lengths)
            if self._doc_lengths
            else 0.0
        )
        self._doc_freq: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            self._doc_freq.update(set(tokens))

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        domain: Domain | None = None,
        source_type: str | None = None,
    ) -> list[SearchResult]:
        if not query.strip() or not self.chunks:
            return []
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        domain_filter = domain or _source_type_to_domain(source_type)
        query_tokens = tokenize_for_sparse(query)
        if not query_tokens:
            return []

        scored: list[SearchResult] = []
        for index, chunk in enumerate(self.chunks):
            if domain_filter is not None and chunk.domain != domain_filter:
                continue
            score = self._bm25_score(query_tokens, index)
            if score <= 0:
                continue
            scored.append(SearchResult.from_chunk(chunk, score=score, method="sparse"))

        scored.sort(key=lambda item: item.score, reverse=True)
        return [
            result.with_score(
                result.score,
                rank_signals={**result.rank_signals, "sparse": rank},
            )
            for rank, result in enumerate(scored[:top_k], start=1)
        ]

    def _bm25_score(self, query_tokens: list[str], doc_index: int) -> float:
        if self._avgdl == 0:
            return 0.0
        term_freq = self._term_freqs[doc_index]
        doc_length = self._doc_lengths[doc_index]
        total_docs = len(self.chunks)
        score = 0.0
        for token, query_count in Counter(query_tokens).items():
            tf = term_freq.get(token, 0)
            if tf == 0:
                continue
            df = self._doc_freq[token]
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self._avgdl)
            if denominator == 0:
                continue
            score += query_count * idf * (tf * (self.k1 + 1)) / denominator
        return score


def sparse_search(
    query: str,
    *,
    chunks: list[Chunk],
    top_k: int = 10,
    source_type: str | None = None,
) -> list[dict[str, object]]:
    retriever = SparseRetriever(chunks)
    return [
        {
            "chunk_id": result.chunk_id,
            "domain": result.domain,
            "score": result.score,
            "title": result.title,
        }
        for result in retriever.search(query, top_k=top_k, source_type=source_type)
    ]


def _source_type_to_domain(source_type: str | None) -> Domain | None:
    if source_type is None:
        return None
    normalized = source_type.lower()
    if normalized in {"tms", "ott", "elderly"}:
        return normalized  # type: ignore[return-value]
    return None
