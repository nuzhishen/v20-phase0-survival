from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Domain = Literal["tms", "ott", "elderly"]


class StrictModel(BaseModel):
    """Day 4 所有外部数据入口的共同基类。

    - `extra="forbid"`：未知字段直接拒绝，延续 Day 1 的严格输入边界。
    - `strict=True`：禁止把字符串 `"5"` 隐式转成整数，避免评估数据被悄悄修正。
    """

    model_config = ConfigDict(extra="forbid", strict=True)


class ChunkPayload(StrictModel):
    """写入向量库的最小知识单元。

    RAG 最怕“只存了一段文本，但不知道来源”。因此 payload 必须同时保留：
    - `chunk_id`：稳定 ID，用于评估命中和 Day 6 证据引用。
    - `domain`：领域隔离字段，Qdrant 会对它创建 keyword payload index。
    - `source`：原始语料文件，方便排查切片问题。
    - `text`：真正参与 embedding 和返回给上层的证据文本。
    - `metadata`：业务字段，例如 error_code、cdn_vendor、risk_level。
    """

    chunk_id: str = Field(min_length=1)
    domain: Domain
    source: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(StrictModel):
    """一次检索返回的一条 Top-K 结果。

    `score` 使用 Qdrant/内存向量库返回的相似度分数，越高越相关。
    `metadata` 原样带回，目的是让调用方能解释“为什么召回这条证据”。
    """

    chunk_id: str
    domain: Domain
    source: str
    title: str
    text: str
    score: float = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(StrictModel):
    """Retriever 对上层暴露的稳定响应格式。"""

    query: str
    domain: Domain | None = None
    top_k: int = Field(ge=1)
    latency_ms: float = Field(ge=0)
    low_confidence: bool
    fallback_reason: str | None = None
    results: list[RetrievalResult]


class EvalQuery(StrictModel):
    """一条评估 Query。

    Day 4 不生成答案，但仍保存 `ground_truth_answer`，用于定义未来 Day 6
    结构化回答应该由哪些证据支撑。
    """

    query_id: str = Field(min_length=1)
    query: str = Field(min_length=2)
    domain: Domain
    expected_chunk_id: str = Field(min_length=1)
    expected_keywords: list[str] = Field(min_length=1)
    ground_truth_context: str = Field(min_length=10)
    ground_truth_answer: str = Field(min_length=10)


class EvalCaseResult(StrictModel):
    """单条 Query 的评估明细，报告失败样例时直接使用。"""

    query_id: str
    domain: Domain
    expected_chunk_id: str
    retrieved_chunk_ids: list[str]
    first_hit_rank: int | None = Field(default=None, ge=1)
    top_score: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    context_precision: float = Field(ge=0, le=1)


class EvalMetrics(StrictModel):
    """Day 4 基线报告需要的 8 个核心指标。"""

    total_queries: int = Field(ge=0)
    recall_at_1: float = Field(ge=0, le=1)
    recall_at_3: float = Field(ge=0, le=1)
    recall_at_5: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    context_precision_at_5: float = Field(ge=0, le=1)
    low_score_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    no_answer_fallback_accuracy: float = Field(ge=0, le=1)
    case_results: list[EvalCaseResult]


class ChunkingConfig(StrictModel):
    """切片器通用配置。

    这里显式校验 `overlap < chunk_size`，防止 FixedChunker 卡死或无限重复。
    """

    chunk_size: int = Field(gt=0)
    overlap: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingConfig":
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        return self

