from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import re
from time import perf_counter

from app.agent.tms_agent import RAGReference, RetrievalResult, RiskLevel


SCORE_THRESHOLD = 0.50
HYBRID_ALPHA = 0.60


@dataclass(frozen=True)
class ErrorKnowledge:
    """保存异常码的兜底知识，支撑 L4 硬编码知识库。"""

    error_code: str
    chunk_id: str
    root_cause: str
    recommended_action: str
    default_risk: RiskLevel


@dataclass(frozen=True)
class CorpusChunk:
    """Day6 本地检索使用的最小 chunk 结构。"""

    chunk_id: str
    title: str
    text: str
    source: str
    domain: str = "tms"
    error_code: str | None = None
    risk_level: str | None = None


@dataclass(frozen=True)
class ScoredChunk:
    """保存检索分数和命中层级，便于生成 RAGReference。"""

    chunk: CorpusChunk
    score: float
    method_scores: dict[str, float]


ERROR_KNOWLEDGE: dict[str, ErrorKnowledge] = {
    "DEVICE_OFFLINE": ErrorKnowledge(
        error_code="DEVICE_OFFLINE",
        chunk_id="tms_e1001",
        root_cause="设备离线超过 72 小时或心跳中断",
        recommended_action="不要直接下发 OTA，先检查电源、网络和 EMQX 在线状态，必要时人工巡检",
        default_risk="HIGH",
    ),
    "OTA_TIMEOUT": ErrorKnowledge(
        error_code="OTA_TIMEOUT",
        chunk_id="tms_e1002",
        root_cause="OTA 下载或安装超时，可能与 CDN、弱网或存储空间有关",
        recommended_action="先选 20 台灰度重试，检查 CDN 命中率、断点续传和设备剩余空间",
        default_risk="MEDIUM",
    ),
    "FIRMWARE_MISMATCH": ErrorKnowledge(
        error_code="FIRMWARE_MISMATCH",
        chunk_id="tms_e1003",
        root_cause="固件版本或板卡适配矩阵不匹配",
        recommended_action="立即阻止升级，冻结固件包，人工确认适配矩阵后再恢复灰度",
        default_risk="HIGH",
    ),
    "HIGH_FAILURE_RATE": ErrorKnowledge(
        error_code="HIGH_FAILURE_RATE",
        chunk_id="tms_e1004",
        root_cause="近 7 天 OTA 失败率过高，可能存在区域网络或灰度比例问题",
        recommended_action="禁止全量升级，只允许 100 台以内试点并观察失败率",
        default_risk="HIGH",
    ),
    "SCRIPT_EXEC_ERROR": ErrorKnowledge(
        error_code="SCRIPT_EXEC_ERROR",
        chunk_id="tms_e1005",
        root_cause="远程脚本执行失败，可能由权限、命令缺失或校验失败导致",
        recommended_action="禁止在生产设备直接重试，必须先在沙箱复现并小批量灰度",
        default_risk="HIGH",
    ),
}


ERROR_CODE_ALIASES = {
    "E1001": "DEVICE_OFFLINE",
    "E1002": "OTA_TIMEOUT",
    "E1003": "FIRMWARE_MISMATCH",
    "E1004": "HIGH_FAILURE_RATE",
    "E1005": "SCRIPT_EXEC_ERROR",
}


def normalize_error_code(error_code: str | None) -> str | None:
    """统一异常码口径，避免 E1002 和 OTA_TIMEOUT 分支重复。"""

    if error_code is None:
        return None
    normalized = error_code.strip().upper()
    return ERROR_CODE_ALIASES.get(normalized, normalized)


def get_error_knowledge(error_code: str | None) -> ErrorKnowledge | None:
    """按统一口径读取 L4 兜底知识。"""

    normalized = normalize_error_code(error_code)
    if normalized is None:
        return None
    return ERROR_KNOWLEDGE.get(normalized)


def retrieve_tms_context(
    query: str,
    *,
    error_code: str | None = None,
    top_k: int = 3,
    force_empty: bool = False,
    force_reranker_failure: bool = False,
    force_hybrid_failure: bool = False,
) -> RetrievalResult:
    """执行 Day6 检索，并把所有失败显式降级。

    这是 ReAct 前唯一的证据入口。它按 Day5 最终配置优先走
    L1: Hybrid alpha=0.6 + MockReranker；失败后退 L2/L3/L4。
    """

    started = perf_counter()
    normalized_error = normalize_error_code(error_code)

    if force_empty:
        return _fallback_to_rule_kb(
            query,
            normalized_error,
            started,
            reason="FORCED_RAG_EMPTY",
        )

    chunks = load_tms_chunks()
    try:
        if force_hybrid_failure:
            raise RuntimeError("forced hybrid failure")
        scored = _hybrid_search(query, chunks, top_k=max(top_k, 3), error_code=normalized_error)
        level = "L1"
        fallback_reason = None
        if force_reranker_failure:
            raise RuntimeError("forced reranker failure")
        scored = _mock_rerank(query, scored, top_k=top_k, error_code=normalized_error)
    except RuntimeError as error:
        if "reranker" in str(error).lower():
            scored = _hybrid_search(query, chunks, top_k=top_k, error_code=normalized_error)
            level = "L2"
            fallback_reason = f"RERANKER_FALLBACK:{error}"
        else:
            scored = _dense_search(query, chunks, top_k=top_k, error_code=normalized_error)
            level = "L3"
            fallback_reason = f"HYBRID_FALLBACK_TO_DENSE:{error}"

    if not scored:
        return _fallback_to_rule_kb(
            query,
            normalized_error,
            started,
            reason="RAG_EMPTY_RESULT",
        )

    confidence = max(item.score for item in scored)
    if confidence < SCORE_THRESHOLD:
        return _fallback_to_rule_kb(
            query,
            normalized_error,
            started,
            reason=f"LOW_CONFIDENCE:{confidence:.4f}",
        )

    return RetrievalResult(
        query=query,
        level_used=level,
        fallback_path=level,
        low_confidence=False,
        confidence=confidence,
        latency_ms=(perf_counter() - started) * 1000,
        references=[_to_reference(item, level) for item in scored[:top_k]],
        fallback_reason=fallback_reason,
    )


def load_tms_chunks() -> list[CorpusChunk]:
    """读取 Day4 TMS 手册，保持 Day6 检索语料来源可追溯。"""

    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "day04_rag_pipeline" / "data" / "corpus" / "tms_ops_manual.md"
    text = path.read_text(encoding="utf-8")
    chunks: list[CorpusChunk] = []
    for title, body in _split_sections(text):
        block = f"{title}\n{body}".strip()
        metadata = _metadata_from_section(block)
        chunks.append(
            CorpusChunk(
                chunk_id=metadata.get("chunk_id", _slug(title)),
                title=title.lstrip("# ").strip(),
                text=block,
                source="tms_ops_manual.md",
                error_code=metadata.get("error_code"),
                risk_level=metadata.get("risk_level"),
            )
        )
    return chunks


def _hybrid_search(
    query: str,
    chunks: list[CorpusChunk],
    *,
    top_k: int,
    error_code: str | None,
) -> list[ScoredChunk]:
    """按 Day5 alpha=0.6 组合 Dense 与 Sparse 分数。"""

    dense = _dense_search(query, chunks, top_k=len(chunks), error_code=error_code)
    sparse = _sparse_search(query, chunks, top_k=len(chunks), error_code=error_code)
    dense_norm = _normalize({item.chunk.chunk_id: item.score for item in dense})
    sparse_norm = _normalize({item.chunk.chunk_id: item.score for item in sparse})
    by_id = {item.chunk.chunk_id: item.chunk for item in [*dense, *sparse]}
    fused: list[ScoredChunk] = []
    for chunk_id, chunk in by_id.items():
        dense_score = dense_norm.get(chunk_id, 0.0)
        sparse_score = sparse_norm.get(chunk_id, 0.0)
        score = HYBRID_ALPHA * dense_score + (1 - HYBRID_ALPHA) * sparse_score
        if error_code and ERROR_KNOWLEDGE.get(error_code, None) and ERROR_KNOWLEDGE[error_code].chunk_id == chunk_id:
            score += 0.30
        fused.append(
            ScoredChunk(
                chunk=chunk,
                score=min(score, 1.0),
                method_scores={
                    "dense_norm": dense_score,
                    "sparse_norm": sparse_score,
                    "hybrid_weighted": min(score, 1.0),
                },
            )
        )
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused[:top_k]


def _dense_search(
    query: str,
    chunks: list[CorpusChunk],
    *,
    top_k: int,
    error_code: str | None,
) -> list[ScoredChunk]:
    """用轻量 n-gram overlap 模拟 Day4/Day5 Dense 语义召回。"""

    query_tokens = Counter(_dense_tokens(_query_with_error(query, error_code)))
    results: list[ScoredChunk] = []
    for chunk in chunks:
        doc_tokens = Counter(_dense_tokens(chunk.text))
        score = _cosine_from_counters(query_tokens, doc_tokens)
        if error_code and ERROR_KNOWLEDGE.get(error_code, None) and ERROR_KNOWLEDGE[error_code].chunk_id == chunk.chunk_id:
            score += 0.25
        if score > 0:
            results.append(
                ScoredChunk(
                    chunk=chunk,
                    score=min(score, 1.0),
                    method_scores={"dense": min(score, 1.0)},
                )
            )
    results.sort(key=lambda item: item.score, reverse=True)
    return results[:top_k]


def _sparse_search(
    query: str,
    chunks: list[CorpusChunk],
    *,
    top_k: int,
    error_code: str | None,
) -> list[ScoredChunk]:
    """用 BM25 风格 token overlap 保留错误码、版本号和英文术语。"""

    query_tokens = Counter(_sparse_tokens(_query_with_error(query, error_code)))
    results: list[ScoredChunk] = []
    for chunk in chunks:
        doc_tokens = Counter(_sparse_tokens(f"{chunk.title}\n{chunk.text}"))
        overlap = sum(min(count, doc_tokens.get(token, 0)) for token, count in query_tokens.items())
        score = overlap / max(sum(query_tokens.values()), 1)
        if error_code and ERROR_KNOWLEDGE.get(error_code, None) and ERROR_KNOWLEDGE[error_code].chunk_id == chunk.chunk_id:
            score += 0.35
        if score > 0:
            results.append(
                ScoredChunk(
                    chunk=chunk,
                    score=min(score, 1.0),
                    method_scores={"sparse": min(score, 1.0)},
                )
            )
    results.sort(key=lambda item: item.score, reverse=True)
    return results[:top_k]


def _mock_rerank(
    query: str,
    candidates: list[ScoredChunk],
    *,
    top_k: int,
    error_code: str | None,
) -> list[ScoredChunk]:
    """按 Day5 MockReranker 思路用标题、精确词和原分数重排。"""

    query_tokens = set(_sparse_tokens(_query_with_error(query, error_code)))
    reranked: list[ScoredChunk] = []
    for rank, item in enumerate(candidates, start=1):
        title_tokens = set(_sparse_tokens(item.chunk.title))
        doc_text = f"{item.chunk.title}\n{item.chunk.text}".lower()
        exact_hits = sum(1 for token in query_tokens if token.isascii() and token in doc_text)
        title_hits = len(query_tokens & title_tokens)
        score = item.score + 0.10 * title_hits + 0.08 * exact_hits + 0.001 / rank
        if error_code and ERROR_KNOWLEDGE.get(error_code, None) and ERROR_KNOWLEDGE[error_code].chunk_id == item.chunk.chunk_id:
            score += 0.20
        method_scores = dict(item.method_scores)
        method_scores["rerank_score"] = score
        reranked.append(
            ScoredChunk(
                chunk=item.chunk,
                score=min(score, 1.0),
                method_scores=method_scores,
            )
        )
    reranked.sort(key=lambda item: item.score, reverse=True)
    return reranked[:top_k]


def _fallback_to_rule_kb(
    query: str,
    error_code: str | None,
    started: float,
    *,
    reason: str,
) -> RetrievalResult:
    """当 RAG 不可靠时退到 Day3 规则知识库，并显式标记 L4。"""

    knowledge = get_error_knowledge(error_code)
    if knowledge is None:
        return RetrievalResult(
            query=query,
            level_used="L4",
            fallback_path="L4",
            low_confidence=True,
            confidence=0.0,
            latency_ms=(perf_counter() - started) * 1000,
            references=[],
            fallback_reason=reason,
        )

    chunk = next(
        (item for item in load_tms_chunks() if item.chunk_id == knowledge.chunk_id),
        CorpusChunk(
            chunk_id=knowledge.chunk_id,
            title=knowledge.error_code,
            text=f"{knowledge.root_cause}\n{knowledge.recommended_action}",
            source="day3_knowledge_base",
            error_code=knowledge.error_code,
            risk_level=knowledge.default_risk,
        ),
    )
    reference = RAGReference(
        chunk_id=chunk.chunk_id,
        section=knowledge.error_code,
        title=chunk.title,
        score=0.50,
        text=chunk.text,
        domain="tms",
        source=chunk.source,
        level_used="L4",
    )
    return RetrievalResult(
        query=query,
        level_used="L4",
        fallback_path="L4",
        low_confidence=True,
        confidence=0.50,
        latency_ms=(perf_counter() - started) * 1000,
        references=[reference],
        fallback_reason=reason,
    )


def _to_reference(item: ScoredChunk, level: str) -> RAGReference:
    """把内部检索命中转换成报告和 ReAct 可消费的证据结构。"""

    return RAGReference(
        chunk_id=item.chunk.chunk_id,
        section=item.chunk.error_code or item.chunk.chunk_id,
        title=item.chunk.title,
        score=item.score,
        text=item.chunk.text,
        domain=item.chunk.domain,
        source=item.chunk.source,
        level_used=level,
    )


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    """按二级标题拆分 Day4 TMS 手册。"""

    sections: list[tuple[str, list[str]]] = []
    title: str | None = None
    body: list[str] = []
    for line in markdown.strip().splitlines():
        if line.startswith("## "):
            if title is not None:
                sections.append((title, body))
            title = line
            body = []
            continue
        if title is not None:
            body.append(line)
    if title is not None:
        sections.append((title, body))
    return [(title, "\n".join(body).strip()) for title, body in sections]


def _metadata_from_section(text: str) -> dict[str, str]:
    """抽取 ChunkID、异常码和风险等级，支撑指标命中判断。"""

    mapping = {"ChunkID": "chunk_id", "异常码": "error_code", "风险等级": "risk_level"}
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if "：" not in line:
            continue
        key, value = line.split("：", 1)
        normalized = mapping.get(key.strip("- * "), key.strip("- * "))
        if value.strip():
            metadata[normalized] = value.strip()
    return metadata


def _query_with_error(query: str, error_code: str | None) -> str:
    """把异常码映射到文档里的 E100x 术语，提高可解释召回。"""

    if error_code is None:
        return query
    knowledge = ERROR_KNOWLEDGE.get(error_code)
    if knowledge is None:
        return f"{query} {error_code}"
    return f"{query} {error_code} {knowledge.chunk_id} {knowledge.root_cause} {knowledge.recommended_action}"


def _dense_tokens(text: str) -> list[str]:
    """生成中文 bi/tri-gram 和 ASCII token，模拟轻量语义召回。"""

    normalized = text.lower()
    compact = [char for char in normalized if not char.isspace()]
    tokens: list[str] = []
    tokens.extend("".join(compact[index : index + 2]) for index in range(len(compact) - 1))
    tokens.extend("".join(compact[index : index + 3]) for index in range(len(compact) - 2))
    tokens.extend(_ascii_tokens(normalized))
    return [token for token in tokens if token]


def _sparse_tokens(text: str) -> list[str]:
    """保留错误码、Android 版本、百分比等精确 token。"""

    normalized = text.lower()
    tokens = _ascii_tokens(normalized)
    for match in re.finditer(r"[\u4e00-\u9fff]+", normalized):
        segment = match.group(0)
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        tokens.extend(segment[index : index + 3] for index in range(len(segment) - 2))
        if len(segment) <= 6:
            tokens.append(segment)
    return [token for token in tokens if token]


def _ascii_tokens(text: str) -> list[str]:
    """抽取英文、数字和下划线/连字符编码。"""

    return re.findall(
        r"(?i)(?:[a-z]+[a-z0-9_-]*[a-z0-9]|[a-z]+|\d+(?:\.\d+)?%?)",
        text,
    )


def _cosine_from_counters(left: Counter[str], right: Counter[str]) -> float:
    """用 Counter 余弦相似度表示轻量 Dense 分数。"""

    if not left or not right:
        return 0.0
    dot = sum(count * right.get(token, 0) for token, count in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    """对单路检索分数做 min-max 归一化，复用 Day5 融合口径。"""

    if not scores:
        return {}
    min_score = min(scores.values())
    max_score = max(scores.values())
    if max_score == min_score:
        return {key: 1.0 if max_score > 0 else 0.0 for key in scores}
    return {key: (value - min_score) / (max_score - min_score) for key, value in scores.items()}


def _slug(text: str) -> str:
    """生成兜底 chunk_id，理论上 Day4 文档都会提供 ChunkID。"""

    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", text.lower()).strip("_")
    return slug or f"chunk_{abs(hash(text))}"

