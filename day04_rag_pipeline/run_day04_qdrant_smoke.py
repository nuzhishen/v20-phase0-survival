from __future__ import annotations

import argparse
from pathlib import Path
import sys


# 允许从任意目录执行脚本，同时仍然导入本日独立的顶层 app 包。
DAY04_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DAY04_DIR))

from app.documents import load_corpus_chunks
from app.embedding import BGEEmbedding, EmbeddingProvider, MockEmbedding
from app.qdrant_client import QdrantClientError, QdrantRAGClient
from app.retriever import Retriever
from app.vector_store import InMemoryVectorStore


def _build_embedder(name: str) -> EmbeddingProvider:
    """根据命令行选择 Embedding。

    - mock：默认选项，速度快、结果稳定，适合日常 smoke test。
    - bge：调用 WSL 中的 sentence-transformers 环境，适合真实向量入库验证。
    """

    if name == "mock":
        return MockEmbedding(vector_size=256)
    if name == "bge":
        embedder = BGEEmbedding()
        if not embedder.is_available():
            raise RuntimeError(
                "WSL BGE Python 不可用，请检查 "
                "/home/aaron/venvs/v20-day4-bge/bin/python"
            )
        return embedder
    raise ValueError(f"unsupported embedder: {name}")


def _build_fallback_store(
    embedder: EmbeddingProvider,
    chunks,
    embeddings: list[list[float]],
) -> InMemoryVectorStore:
    """构建内存兜底向量库。

    真实 Qdrant smoke 如果网络超时，Retriever 可以退回内存库；
    这对应计划里的 ChatGPT 稳定性兜底。
    """

    fallback = InMemoryVectorStore()
    fallback.create_collection(embedder.vector_size)
    fallback.upsert_chunks(chunks, embeddings)
    return fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 Day 4 Qdrant smoke test")
    parser.add_argument("--url", default=None, help="Qdrant URL，默认读取 QDRANT_URL 或 localhost")
    parser.add_argument("--collection", default="phase0_day4_context_smoke", help="测试 collection 名称")
    parser.add_argument("--embedder", choices=["mock", "bge"], default="mock", help="选择 Mock 或 BGE 向量")
    parser.add_argument("--top-k", type=int, default=3, help="每条 smoke query 返回几条结果")
    args = parser.parse_args()

    chunks = load_corpus_chunks()
    embedder = _build_embedder(args.embedder)
    embeddings = embedder.embed_texts([chunk.text for chunk in chunks])

    qdrant = QdrantRAGClient(
        url=args.url,
        collection_name=args.collection,
        timeout_seconds=30,
    )
    fallback = _build_fallback_store(embedder, chunks, embeddings)
    retriever = Retriever(
        embedder=embedder,
        vector_store=qdrant,
        fallback_store=fallback,
        score_threshold=0.2,
    )

    try:
        qdrant.create_collection(embedder.vector_size)
        qdrant.upsert_chunks(chunks, embeddings)
    except QdrantClientError as error:
        print(f"Qdrant smoke failed before search: {error}", file=sys.stderr)
        return 2

    queries = [
        ("设备离线超过72小时怎么处理？", "tms"),
        ("直播卡顿先查 CDN 还是播放器？", "ott"),
        ("老人血压 160/100 应该怎么处理？", "elderly"),
    ]
    for query, domain in queries:
        response = retriever.retrieve(query, top_k=args.top_k, domain=domain)  # type: ignore[arg-type]
        ids = ", ".join(f"{item.chunk_id}:{item.score:.3f}" for item in response.results)
        print(
            f"domain={domain} low_confidence={response.low_confidence} "
            f"fallback={response.fallback_reason or '-'} results=[{ids}]"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
