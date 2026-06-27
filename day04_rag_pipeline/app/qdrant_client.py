from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas import ChunkPayload, Domain, RetrievalResult
from app.vector_store import VectorStore


class QdrantClientError(RuntimeError):
    """Qdrant 连接、建库或检索失败时抛出。"""


class QdrantRAGClient(VectorStore):
    """最小 Qdrant REST 客户端。

    当前 Windows `.venv` 是 Python 3.14，`qdrant-client` 轮子不可用。
    为了保证代码在本机可执行，这里不依赖 SDK，而是直接调用 Qdrant REST API。

    仍然保留训练令要求的工程点：
    - 手写 Collection 配置。
    - HNSW `m=16`、`ef_construct=100`。
    - 查询时 `hnsw_ef=64`。
    - `domain` payload keyword index。
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str = "phase0_day4_context",
        hnsw_m: int = 16,
        ef_construct: int = 100,
        hnsw_ef: int = 64,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.url = (url or os.getenv("QDRANT_URL") or "http://localhost:6333").rstrip("/")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        self.hnsw_m = hnsw_m
        self.ef_construct = ef_construct
        self.hnsw_ef = hnsw_ef
        self.timeout_seconds = timeout_seconds
        self.vector_size: int | None = None

    def create_collection(self, vector_size: int) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive")
        self.vector_size = vector_size

        # 先删后建，保证 Day 4 训练可重复；正式生产应使用版本化 collection。
        if self.collection_exists():
            self.delete_collection()

        self._request(
            "PUT",
            f"/collections/{self.collection_name}",
            {
                "vectors": {"size": vector_size, "distance": "Cosine"},
                "hnsw_config": {
                    "m": self.hnsw_m,
                    "ef_construct": self.ef_construct,
                },
            },
        )
        self.create_domain_payload_index()

    def create_domain_payload_index(self) -> None:
        self._request(
            "PUT",
            f"/collections/{self.collection_name}/index",
            {"field_name": "domain", "field_schema": "keyword"},
        )

    def collection_exists(self) -> bool:
        try:
            self._request("GET", f"/collections/{self.collection_name}")
            return True
        except QdrantClientError:
            return False

    def delete_collection(self) -> None:
        self._request("DELETE", f"/collections/{self.collection_name}")

    def upsert_chunks(
        self,
        chunks: list[ChunkPayload],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        points: list[dict[str, Any]] = []
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True), start=1):
            self._validate_vector(embedding)
            # Qdrant REST 支持数字或 UUID。这里用稳定数字 ID，并把 chunk_id 放进 payload。
            # 生产可改为 UUIDv5(chunk_id)，Day 4 保持简单可读。
            points.append(
                {
                    "id": index,
                    "vector": embedding,
                    "payload": chunk.model_dump(),
                }
            )

        for start in range(0, len(points), 100):
            batch = points[start : start + 100]
            self._request(
                "PUT",
                f"/collections/{self.collection_name}/points?wait=true",
                {"points": batch},
            )

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

        payload: dict[str, Any] = {
            "query": query_vector,
            "limit": top_k,
            "with_payload": True,
            "params": {"hnsw_ef": self.hnsw_ef},
        }
        if domain_filter is not None:
            payload["filter"] = {
                "must": [
                    {"key": "domain", "match": {"value": domain_filter}},
                ]
            }

        data = self._request(
            "POST",
            f"/collections/{self.collection_name}/points/query",
            payload,
        )
        raw_points = data.get("result", {}).get("points", data.get("result", []))
        results: list[RetrievalResult] = []
        for point in raw_points:
            score = float(point.get("score", 0.0))
            if score < score_threshold:
                continue
            payload_data = point.get("payload") or {}
            results.append(
                RetrievalResult(
                    chunk_id=payload_data["chunk_id"],
                    domain=payload_data["domain"],
                    source=payload_data["source"],
                    title=payload_data["title"],
                    text=payload_data["text"],
                    score=score,
                    metadata=payload_data.get("metadata") or {},
                )
            )
        return results

    def _validate_vector(self, vector: list[float]) -> None:
        if self.vector_size is None:
            raise RuntimeError("collection has not been created")
        if len(vector) != self.vector_size:
            raise ValueError(
                f"vector size mismatch: expected {self.vector_size}, got {len(vector)}"
            )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        request = Request(
            f"{self.url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise QdrantClientError(f"Qdrant HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise QdrantClientError(f"Qdrant connection failed: {error}") from error

        if not content:
            return {}
        return json.loads(content)

