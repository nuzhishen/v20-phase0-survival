from __future__ import annotations

from enum import StrEnum

from app.rag.types import SearchResult


class FusionMethod(StrEnum):
    WEIGHTED = "weighted"
    LINEAR = "linear"
    RRF = "rrf"


def normalize_scores(results: list[SearchResult]) -> dict[str, float]:
    """Min-max normalize one retrieval result list for a single query."""

    if not results:
        return {}
    scores = [result.score for result in results]
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return {result.chunk_id: 1.0 if max_score > 0 else 0.0 for result in results}
    return {
        result.chunk_id: (result.score - min_score) / (max_score - min_score)
        for result in results
    }


def fuse_weighted(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    *,
    alpha: float,
    top_k: int,
) -> list[SearchResult]:
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    dense_norm = normalize_scores(dense_results)
    sparse_norm = normalize_scores(sparse_results)
    by_id = _result_union(dense_results, sparse_results)
    fused: list[SearchResult] = []
    for chunk_id, result in by_id.items():
        dense_score = dense_norm.get(chunk_id, 0.0)
        sparse_score = sparse_norm.get(chunk_id, 0.0)
        score = alpha * dense_score + (1 - alpha) * sparse_score
        method_scores = dict(result.method_scores)
        method_scores.update(
            {
                "dense_norm": dense_score,
                "sparse_norm": sparse_score,
                "hybrid_weighted": score,
            }
        )
        fused.append(
            result.with_score(
                score,
                method_scores=method_scores,
                rank_signals=dict(result.rank_signals),
            )
        )
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused[:top_k]


def fuse_linear(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    *,
    lambda_value: float,
    top_k: int,
) -> list[SearchResult]:
    return fuse_weighted(
        dense_results,
        sparse_results,
        alpha=lambda_value,
        top_k=top_k,
    )


def fuse_rrf(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    *,
    k: int = 60,
    top_k: int,
) -> list[SearchResult]:
    if k <= 0:
        raise ValueError("k must be positive")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    by_id = _result_union(dense_results, sparse_results)
    dense_rank = {result.chunk_id: rank for rank, result in enumerate(dense_results, start=1)}
    sparse_rank = {result.chunk_id: rank for rank, result in enumerate(sparse_results, start=1)}
    fused: list[SearchResult] = []
    for chunk_id, result in by_id.items():
        score = 0.0
        rank_signals = dict(result.rank_signals)
        if chunk_id in dense_rank:
            score += 1 / (k + dense_rank[chunk_id])
            rank_signals["dense"] = dense_rank[chunk_id]
        if chunk_id in sparse_rank:
            score += 1 / (k + sparse_rank[chunk_id])
            rank_signals["sparse"] = sparse_rank[chunk_id]
        method_scores = dict(result.method_scores)
        method_scores["hybrid_rrf"] = score
        fused.append(
            result.with_score(
                score,
                method_scores=method_scores,
                rank_signals=rank_signals,
            )
        )
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused[:top_k]


def fuse_results(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    *,
    method: FusionMethod,
    alpha: float = 0.5,
    top_k: int,
    rrf_k: int = 60,
) -> list[SearchResult]:
    if method == FusionMethod.WEIGHTED:
        return fuse_weighted(dense_results, sparse_results, alpha=alpha, top_k=top_k)
    if method == FusionMethod.LINEAR:
        return fuse_linear(dense_results, sparse_results, lambda_value=alpha, top_k=top_k)
    if method == FusionMethod.RRF:
        return fuse_rrf(dense_results, sparse_results, k=rrf_k, top_k=top_k)
    raise ValueError(f"unsupported fusion method: {method}")


def _result_union(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
) -> dict[str, SearchResult]:
    by_id: dict[str, SearchResult] = {}
    for result in [*dense_results, *sparse_results]:
        existing = by_id.get(result.chunk_id)
        if existing is None:
            by_id[result.chunk_id] = result
            continue
        method_scores = dict(existing.method_scores)
        method_scores.update(result.method_scores)
        rank_signals = dict(existing.rank_signals)
        rank_signals.update(result.rank_signals)
        by_id[result.chunk_id] = existing.with_score(
            max(existing.score, result.score),
            method_scores=method_scores,
            rank_signals=rank_signals,
        )
    return by_id
