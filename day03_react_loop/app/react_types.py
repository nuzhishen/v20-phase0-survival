from dataclasses import dataclass, field
from typing import Any, Literal


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class DiagnosisResult:
    device_id: str
    error_code: str
    root_cause: str
    evidence: list[str]
    recommended_action: str
    risk_level: RiskLevel
    require_hitl: bool
    fallback_reason: str | None = None


@dataclass
class ReactState:
    device_id: str
    error_code: str
    failure_rate_7d: float
    region: str
    android_version: str
    batch_size: int = 1
    step: int = 0
    observations: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
