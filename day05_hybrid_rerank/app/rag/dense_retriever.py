from __future__ import annotations

import hashlib
import math

from app.rag.types import Chunk, Domain, SearchResult


_KEY_TERMS = [
    "设备离线",
    "离线",
    "72",
    "ota",
    "下载",
    "超时",
    "固件",
    "版本",
    "不一致",
    "批量",
    "失败",
    "脚本",
    "emqx",
    "证书",
    "存储",
    "空间",
    "回滚",
    "cdn",
    "带宽",
    "时钟",
    "ntp",
    "直播",
    "卡顿",
    "播放器",
    "首帧",
    "drm",
    "license",
    "卡死",
    "灰屏",
    "epg",
    "节目单",
    "字幕",
    "音画",
    "同步",
    "码率",
    "清晰度",
    "黑屏",
    "403",
    "token",
    "鉴权",
    "回看",
    "高血压",
    "血压",
    "血糖",
    "低血糖",
    "跌倒",
    "胸痛",
    "服药",
    "睡眠",
    "运动",
    "饮食",
    "脱水",
    "发热",
    "认知",
    "走失",
    "疼痛",
    "便秘",
    "水肿",
    "体重",
    "呼吸困难",
    "呼吸",
]


class MockDenseRetriever:
    """Day 5 dense baseline compatible with Day 4 MockEmbedding behavior."""

    def __init__(
        self,
        chunks: list[Chunk],
        *,
        vector_size: int = 256,
        score_threshold: float = 0.2,
    ) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive")
        self.chunks = chunks
        self.vector_size = vector_size
        self.score_threshold = score_threshold
        self._vectors = {
            # Preserve Day 4 dense baseline: Day 4 embeds `chunk.text` only.
            # Sparse may index metadata, but Dense must stay comparable.
            chunk.chunk_id: self._embed(chunk.text)
            for chunk in self.chunks
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        domain: Domain | None = None,
    ) -> list[SearchResult]:
        if not query.strip():
            return []
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        query_vector = self._embed(query)
        scored: list[SearchResult] = []
        for chunk in self.chunks:
            if domain is not None and chunk.domain != domain:
                continue
            score = _cosine_similarity(query_vector, self._vectors[chunk.chunk_id])
            if score < self.score_threshold:
                continue
            scored.append(SearchResult.from_chunk(chunk, score=score, method="dense"))

        scored.sort(key=lambda item: item.score, reverse=True)
        return [
            result.with_score(
                result.score,
                rank_signals={**result.rank_signals, "dense": rank},
            )
            for rank, result in enumerate(scored[:top_k], start=1)
        ]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.vector_size
        for token in _dense_tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.vector_size
            vector[bucket] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def _dense_tokens(text: str) -> list[str]:
    normalized = text.lower()
    chars = [char for char in normalized if not char.isspace()]
    tokens: list[str] = []
    tokens.extend("".join(chars[index : index + 2]) for index in range(len(chars) - 1))
    tokens.extend("".join(chars[index : index + 3]) for index in range(len(chars) - 2))

    for term in _KEY_TERMS:
        if term in normalized:
            tokens.extend([f"term:{term}"] * 12)

    current_ascii: list[str] = []
    for char in normalized:
        if char.isascii() and (char.isalnum() or char in {"_", "-"}):
            current_ascii.append(char)
        else:
            if current_ascii:
                tokens.append("".join(current_ascii))
                current_ascii.clear()
    if current_ascii:
        tokens.append("".join(current_ascii))
    return [token for token in tokens if token]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    return max(dot / (left_norm * right_norm), 0.0)
