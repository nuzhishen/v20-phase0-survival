from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Domain = Literal["tms", "ott", "elderly"]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    domain: Domain
    source: str
    title: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    query: str
    domain: Domain
    expected_chunk_id: str
    expected_keywords: tuple[str, ...]
    ground_truth_context: str
    ground_truth_answer: str


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    domain: Domain
    source: str
    title: str
    text: str
    score: float
    metadata: dict[str, str] = field(default_factory=dict)
    method_scores: dict[str, float] = field(default_factory=dict)
    rank_signals: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_chunk(
        cls,
        chunk: Chunk,
        *,
        score: float,
        method: str,
        rank: int | None = None,
    ) -> "SearchResult":
        rank_signals = {} if rank is None else {method: rank}
        return cls(
            chunk_id=chunk.chunk_id,
            domain=chunk.domain,
            source=chunk.source,
            title=chunk.title,
            text=chunk.text,
            score=score,
            metadata=dict(chunk.metadata),
            method_scores={method: score},
            rank_signals=rank_signals,
        )

    def with_score(
        self,
        score: float,
        *,
        method_scores: dict[str, float] | None = None,
        rank_signals: dict[str, int] | None = None,
    ) -> "SearchResult":
        return SearchResult(
            chunk_id=self.chunk_id,
            domain=self.domain,
            source=self.source,
            title=self.title,
            text=self.text,
            score=score,
            metadata=dict(self.metadata),
            method_scores=method_scores or dict(self.method_scores),
            rank_signals=rank_signals or dict(self.rank_signals),
        )
