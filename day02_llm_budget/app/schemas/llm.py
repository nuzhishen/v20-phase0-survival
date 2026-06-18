from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    # 统一入口模型：禁止额外字段 + 严格类型，避免脏数据进入 LLM 调用层。
    model_config = ConfigDict(extra="forbid", strict=True)


class ChatMessage(StrictModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)


class LLMRequest(StrictModel):
    # estimated_cost_cents 是 Pre-flight 预算检查使用的估算成本，
    # 必须在真实调用 Provider 之前计算并校验。
    request_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_tokens: int = Field(ge=1)
    task_type: Literal["tms_diagnosis", "elderly_medication", "ott_report"]
    estimated_cost_cents: Decimal = Field(ge=0)


class TokenUsage(StrictModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_cents: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "TokenUsage":
        # Provider 返回的 usage 是成本审计依据，total 不一致时必须拒绝。
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")
        return self


class LLMResponse(StrictModel):
    request_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    content: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: TokenUsage
    finish_reason: str | None
    # compliant 表示业务或安全校验结果，用于后续合规率统计。
    latency_ms: int = Field(ge=0)
    compliant: bool
    created_at: datetime = Field(default_factory=datetime.now)
