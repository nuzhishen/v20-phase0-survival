from __future__ import annotations

from app.rag.dense_retriever import MockDenseRetriever
from app.rag.hybrid_fusion import FusionMethod, fuse_results
from app.rag.reranker import Reranker
from app.rag.sparse_retriever import SparseRetriever
from app.rag.types import Domain, SearchResult


class HybridRetriever:
    def __init__(
        self,
        *,
        dense: MockDenseRetriever,
        sparse: SparseRetriever,
        reranker: Reranker | None = None,
    ) -> None:
        self.dense = dense
        self.sparse = sparse
        self.reranker = reranker

    def search(
        self,
        query: str,
        *,
        domain: Domain | None = None,
        top_k: int = 5,
        candidate_pool: int = 10,
        fusion_method: FusionMethod = FusionMethod.WEIGHTED,
        alpha: float = 0.5,
        rerank: bool = False,
        expected_keywords: tuple[str, ...] = (),
    ) -> list[SearchResult]:
        if not query.strip():
            return []
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if candidate_pool < top_k:
            raise ValueError("candidate_pool must be >= top_k")

        dense_results = self.dense.search(query, top_k=candidate_pool, domain=domain)
        sparse_results = self.sparse.search(query, top_k=candidate_pool, domain=domain)
        fused = fuse_results(
            dense_results,
            sparse_results,
            method=fusion_method,
            alpha=alpha,
            top_k=candidate_pool,
        )
        if rerank:
            if self.reranker is None:
                raise RuntimeError("reranker is not configured")
            return self.reranker.rerank(
                query,
                fused,
                top_k=top_k,
                expected_keywords=expected_keywords,
            )
        return fused[:top_k]
