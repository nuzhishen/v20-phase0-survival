import json

import pytest
from pydantic import ValidationError

from app.chunker import FixedChunker
from app.documents import load_corpus_chunks
from app.embedding import MockEmbedding, ZeroEmbedding
from app.qdrant_client import QdrantRAGClient
from app.rag_pipeline import build_in_memory_pipeline, evaluate_retriever, load_eval_queries
from app.retriever import Retriever
from app.schemas import ChunkPayload, ChunkingConfig
from app.vector_store import InMemoryVectorStore


def test_corpus_has_required_domain_coverage() -> None:
    """三份语料都必须至少产出 10 个 chunk。

    这是 Day 4 评估的基本盘：没有足够业务语料，后面的 Recall/MRR 都没有意义。
    """

    chunks = load_corpus_chunks()
    by_domain = {
        "tms": [chunk for chunk in chunks if chunk.domain == "tms"],
        "ott": [chunk for chunk in chunks if chunk.domain == "ott"],
        "elderly": [chunk for chunk in chunks if chunk.domain == "elderly"],
    }

    assert len(by_domain["tms"]) >= 10
    assert len(by_domain["ott"]) >= 10
    assert len(by_domain["elderly"]) >= 10
    assert "tms_e1001" in {chunk.chunk_id for chunk in chunks}
    assert "ott_q001" in {chunk.chunk_id for chunk in chunks}
    assert "elderly_001" in {chunk.chunk_id for chunk in chunks}


def test_chunk_payload_rejects_unknown_domain_and_extra_fields() -> None:
    """ChunkPayload 是向量库入口，必须强类型、拒绝未知字段。"""

    with pytest.raises(ValidationError):
        ChunkPayload(
            chunk_id="bad",
            domain="finance",
            source="bad.md",
            title="bad",
            text="这是一段足够长但领域非法的测试文本。",
            metadata={},
        )

    with pytest.raises(ValidationError):
        ChunkPayload(
            chunk_id="bad",
            domain="tms",
            source="bad.md",
            title="bad",
            text="这是一段足够长但包含未知字段的测试文本。",
            metadata={},
            unexpected=True,
        )


def test_chunking_config_rejects_invalid_overlap() -> None:
    """overlap >= chunk_size 会导致固定切片器重复甚至死循环，必须拒绝。"""

    with pytest.raises(ValidationError):
        ChunkingConfig(chunk_size=100, overlap=100)


def test_fixed_chunker_keeps_elderly_section_ids() -> None:
    text = """# Guide

## 高血压
ChunkID：elderly_custom
主题：高血压
监测频率：每天一次。
正常范围：90/60 到 140/90。
异常处理：连续异常联系医生。
禁忌：不要自行加药。
"""
    chunks = FixedChunker(ChunkingConfig(chunk_size=300, overlap=20)).chunk(
        text,
        source="guide.md",
    )

    assert chunks[0].chunk_id == "elderly_custom"
    assert chunks[0].domain == "elderly"
    assert "不要自行加药" in chunks[0].text


def test_mock_embedding_is_deterministic_and_keyword_sensitive() -> None:
    embedder = MockEmbedding(vector_size=64)

    first = embedder.embed_query("直播卡顿 CDN 播放器")
    second = embedder.embed_query("直播卡顿 CDN 播放器")
    different = embedder.embed_query("老人血压 160/100")

    assert first == second
    assert first != different
    assert len(first) == 64


def test_retriever_returns_top_k_with_metadata() -> None:
    retriever, _ = build_in_memory_pipeline(score_threshold=0.2)

    response = retriever.retrieve("直播卡顿怎么排查 CDN 播放器", domain="ott", top_k=3)

    assert response.low_confidence is False
    assert response.results
    assert response.results[0].domain == "ott"
    assert response.results[0].chunk_id.startswith("ott_")
    assert response.results[0].metadata
    assert response.latency_ms >= 0


def test_retriever_rejects_invalid_query_and_top_k() -> None:
    retriever, _ = build_in_memory_pipeline()

    with pytest.raises(ValueError):
        retriever.retrieve("", domain="tms")
    with pytest.raises(ValueError):
        retriever.retrieve("设备离线", domain="tms", top_k=0)
    with pytest.raises(ValidationError):
        retriever.retrieve("设备离线", domain="finance")  # type: ignore[arg-type]


def test_zero_embedding_triggers_low_confidence() -> None:
    chunks = load_corpus_chunks()
    embedder = ZeroEmbedding(vector_size=8)
    store = InMemoryVectorStore()
    store.create_collection(embedder.vector_size)
    store.upsert_chunks(chunks, embedder.embed_texts([chunk.text for chunk in chunks]))
    retriever = Retriever(embedder=embedder, vector_store=store, score_threshold=0.1)

    response = retriever.retrieve("直播卡顿", domain="ott")

    assert response.low_confidence is True
    assert response.fallback_reason == "NO_RELEVANT_CONTEXT"
    assert response.results == []


def test_eval_queries_are_30_and_have_ground_truth() -> None:
    queries = load_eval_queries()

    assert len(queries) == 30
    assert sum(query.domain == "tms" for query in queries) == 10
    assert sum(query.domain == "ott" for query in queries) == 10
    assert sum(query.domain == "elderly" for query in queries) == 10
    assert all(query.expected_chunk_id for query in queries)
    assert all(query.ground_truth_context for query in queries)
    assert all(query.ground_truth_answer for query in queries)


def test_day04_eval_metrics_meet_dense_baseline() -> None:
    """用 MockEmbedding 建立可重复 Dense 基线。

    真实 BGE 指标可能随模型和语料调整变化；单元测试只锁定工程链路和最低基线。
    """

    retriever, _ = build_in_memory_pipeline(score_threshold=0.2)
    metrics = evaluate_retriever(retriever, load_eval_queries(), top_k=5)

    assert metrics.total_queries == 30
    assert metrics.recall_at_1 >= 0.40
    assert metrics.recall_at_3 >= 0.60
    assert metrics.recall_at_5 >= 0.50
    assert metrics.mrr >= 0.60
    assert metrics.context_precision_at_5 >= 0.60
    assert metrics.low_score_rate < 0.20
    assert metrics.no_answer_fallback_accuracy >= 0.80
    assert metrics.average_latency_ms < 200


def test_retriever_falls_back_when_primary_store_fails() -> None:
    """模拟 Qdrant 断开时降级到 InMemoryVectorStore。"""

    class BrokenStore(InMemoryVectorStore):
        def search(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("qdrant timeout")

    embedder = MockEmbedding(vector_size=64)
    chunks = load_corpus_chunks()
    fallback = InMemoryVectorStore()
    fallback.create_collection(embedder.vector_size)
    fallback.upsert_chunks(chunks, embedder.embed_texts([chunk.text for chunk in chunks]))
    retriever = Retriever(
        embedder=embedder,
        vector_store=BrokenStore(),
        fallback_store=fallback,
        score_threshold=0.2,
    )

    response = retriever.retrieve("设备离线超过72小时", domain="tms")

    assert response.low_confidence is False
    assert response.fallback_reason == "PRIMARY_VECTOR_STORE_FAILED:RuntimeError"
    assert response.results[0].domain == "tms"


def test_qdrant_client_writes_hnsw_and_payload_index_requests() -> None:
    """不依赖真实 Qdrant，用 fake request 验证 REST 客户端请求形态。"""

    calls: list[tuple[str, str, dict | None]] = []

    class FakeQdrant(QdrantRAGClient):
        def collection_exists(self) -> bool:
            return False

        def _request(self, method, path, payload=None):  # type: ignore[no-untyped-def]
            calls.append((method, path, payload))
            if path.endswith("/points/query"):
                return {
                    "result": {
                        "points": [
                            {
                                "score": 0.99,
                                "payload": {
                                    "chunk_id": "tms_e1001",
                                    "domain": "tms",
                                    "source": "tms_ops_manual.md",
                                    "title": "E1001",
                                    "text": "设备离线超过72小时需要现场检修。",
                                    "metadata": {"error_code": "E1001"},
                                },
                            }
                        ]
                    }
                }
            return {}

    client = FakeQdrant(collection_name="test_collection")
    client.create_collection(256)
    result = client.search([0.1] * 256, top_k=1, domain_filter="tms", score_threshold=0.5)

    create_payload = calls[0][2]
    assert create_payload["hnsw_config"]["m"] == 16  # type: ignore[index]
    assert create_payload["hnsw_config"]["ef_construct"] == 100  # type: ignore[index]
    assert calls[1][1] == "/collections/test_collection/index"
    assert calls[1][2]["field_name"] == "domain"  # type: ignore[index]
    query_payload = calls[2][2]
    assert query_payload["params"]["hnsw_ef"] == 64  # type: ignore[index]
    assert query_payload["filter"]["must"][0]["match"]["value"] == "tms"  # type: ignore[index]
    assert result[0].chunk_id == "tms_e1001"


def test_jsonl_file_is_valid_json_per_line() -> None:
    """JSONL 评估集必须逐行可解析，方便后续脚本和报告复用。"""

    from app.rag_pipeline import EVAL_PATH

    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        assert isinstance(json.loads(line), dict)

