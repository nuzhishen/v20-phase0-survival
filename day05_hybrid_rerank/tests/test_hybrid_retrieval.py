import pytest

from app.rag.compare_eval import run_comparison
from app.rag.data_loader import load_corpus_chunks, load_eval_queries
from app.rag.dense_retriever import MockDenseRetriever
from app.rag.hybrid_fusion import FusionMethod, fuse_rrf, fuse_weighted
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import BGEReranker, FallbackReranker, MockReranker
from app.rag.sparse_retriever import SparseRetriever, tokenize_for_sparse

def test_tokenizer_preserves_error_codes_versions_and_numbers() -> None:
    tokens = tokenize_for_sparse("OTA_TIMEOUT Android 11 TMS-GD-100 播放地址403 /data 300MB")

    assert "ota_timeout" in tokens
    assert "android" in tokens
    assert "11" in tokens
    assert "tms-gd-100" in tokens
    assert "403" in tokens
    assert "data" in tokens
    assert "300mb" in tokens


def test_sparse_retriever_returns_topk_with_domain_filter() -> None:
    chunks = load_corpus_chunks()
    retriever = SparseRetriever(chunks)

    results = retriever.search("播放地址 403 是不是 CDN 故障？", top_k=3, domain="ott")

    assert results
    assert results[0].domain == "ott"
    assert results[0].chunk_id == "ott_q009"
    assert all(result.domain == "ott" for result in results)


def test_sparse_empty_query_and_empty_index_do_not_crash() -> None:
    chunks = load_corpus_chunks()
    assert SparseRetriever(chunks).search("", top_k=3) == []
    assert SparseRetriever([]).search("OTA_TIMEOUT", top_k=3) == []
    assert SparseRetriever(chunks).search("量子咖啡双色球", top_k=3, domain="tms") == []


def test_weighted_fusion_alpha_boundaries() -> None:
    chunks = load_corpus_chunks()
    dense = MockDenseRetriever(chunks)
    sparse = SparseRetriever(chunks)
    dense_results = dense.search("设备离线超过72小时", top_k=5, domain="tms")
    sparse_results = sparse.search("设备离线超过72小时", top_k=5, domain="tms")

    sparse_only = fuse_weighted(dense_results, sparse_results, alpha=0.0, top_k=3)
    dense_only = fuse_weighted(dense_results, sparse_results, alpha=1.0, top_k=3)

    assert sparse_only
    assert dense_only
    assert sparse_only[0].method_scores["sparse_norm"] >= 0
    assert dense_only[0].method_scores["dense_norm"] >= 0
    with pytest.raises(ValueError):
        fuse_weighted(dense_results, sparse_results, alpha=1.1, top_k=3)


def test_rrf_fusion_returns_rank_based_union() -> None:
    chunks = load_corpus_chunks()
    dense = MockDenseRetriever(chunks)
    sparse = SparseRetriever(chunks)
    dense_results = dense.search("CDN 回源超时首帧慢", top_k=5, domain="ott")
    sparse_results = sparse.search("CDN 回源超时首帧慢", top_k=5, domain="ott")

    fused = fuse_rrf(dense_results, sparse_results, top_k=5)

    assert fused
    assert all("hybrid_rrf" in result.method_scores for result in fused)
    assert fused[0].score >= fused[-1].score


def test_hybrid_retriever_and_mock_reranker_return_topk() -> None:
    chunks = load_corpus_chunks()
    retriever = HybridRetriever(
        dense=MockDenseRetriever(chunks),
        sparse=SparseRetriever(chunks),
        reranker=MockReranker(),
    )

    hybrid = retriever.search("设备时间漂移10分钟影响证书校验怎么办？", domain="tms", top_k=3)
    reranked = retriever.search(
        "设备时间漂移10分钟影响证书校验怎么办？",
        domain="tms",
        top_k=3,
        rerank=True,
    )

    assert len(hybrid) <= 3
    assert len(reranked) <= 3
    assert reranked[0].domain == "tms"
    assert "rerank_score" in reranked[0].method_scores


def test_bge_unavailable_falls_back_to_mock_reranker() -> None:
    chunks = load_corpus_chunks()
    dense = MockDenseRetriever(chunks)
    candidates = dense.search("直播卡顿怎么排查", top_k=5, domain="ott")
    reranker = FallbackReranker(primary=BGEReranker(available=False), fallback=MockReranker())

    results = reranker.rerank("直播卡顿怎么排查", candidates, top_k=3)

    assert results
    assert reranker.last_fallback_reason is not None
    assert "RuntimeError" in reranker.last_fallback_reason


def test_reranker_handles_empty_candidates() -> None:
    assert MockReranker().rerank("直播卡顿", [], top_k=3) == []


def test_eval_queries_are_reused_from_day04() -> None:
    queries = load_eval_queries()

    assert len(queries) == 30
    assert sum(query.domain == "tms" for query in queries) == 10
    assert sum(query.domain == "ott" for query in queries) == 10
    assert sum(query.domain == "elderly" for query in queries) == 10


def test_compare_eval_runs_all_required_methods_without_writing_reports() -> None:
    summary = run_comparison(write_reports=False)
    method_names = {metric.name for metric in summary.metrics}

    assert "Dense Only" in method_names
    assert "Sparse BM25 Only" in method_names
    assert "Hybrid alpha=0.2" in method_names
    assert "Hybrid alpha=0.4" in method_names
    assert "Hybrid alpha=0.5" in method_names
    assert "Hybrid alpha=0.6" in method_names
    assert "Hybrid alpha=0.8" in method_names
    assert "Hybrid RRF" in method_names
    assert any("MockReranker" in name for name in method_names)
    assert summary.best_final.total_queries == 30
    assert summary.best_final.recall_at_3 >= 0
