from collections.abc import Callable
from typing import Any

from app.knowledge_base import UNKNOWN_ERROR_FALLBACK, get_error_knowledge
from app.react_types import RiskLevel, ToolResult


ToolFunction = Callable[..., ToolResult]


DEVICE_STATUS: dict[str, dict[str, Any]] = {
    "TMS-GD-001": {
        "found": True,
        "online": False,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.1",
        "last_seen": "2026-06-17T08:30:00+08:00",
    },
    "TMS-GD-002": {
        "found": True,
        "online": True,
        "region": "华南",
        "android_version": "12",
        "firmware_version": "2.4.3",
        "last_seen": "2026-06-24T09:10:00+08:00",
    },
    "TMS-HD-003": {
        "found": True,
        "online": True,
        "region": "华东",
        "android_version": "10",
        "firmware_version": "2.3.9",
        "last_seen": "2026-06-24T09:08:00+08:00",
    },
}


def query_device_status(device_id: str) -> ToolResult:
    data = DEVICE_STATUS.get(device_id)
    if data is None:
        return ToolResult(ok=True, data={"found": False, "device_id": device_id})
    return ToolResult(ok=True, data={"device_id": device_id, **data})


def lookup_error_knowledge(error_code: str) -> ToolResult:
    knowledge = get_error_knowledge(error_code)
    if knowledge is None:
        return ToolResult(
            ok=True,
            data={
                "found": False,
                "error_code": error_code,
                "fallback_reason": UNKNOWN_ERROR_FALLBACK,
            },
        )
    return ToolResult(
        ok=True,
        data={
            "found": True,
            "error_code": knowledge.error_code,
            "root_cause": knowledge.root_cause,
            "recommended_action": knowledge.recommended_action,
            "default_risk": knowledge.default_risk,
        },
    )


def estimate_operation_risk(
    failure_rate_7d: float,
    error_code: str,
    batch_size: int,
) -> ToolResult:
    knowledge = get_error_knowledge(error_code)
    risk: RiskLevel = knowledge.default_risk if knowledge else "HIGH"

    if batch_size > 100 or failure_rate_7d >= 0.10:
        risk = "HIGH"
    elif knowledge is None:
        risk = "HIGH"
    elif failure_rate_7d == 0 and knowledge.default_risk != "HIGH":
        risk = "LOW" if error_code != "DEVICE_OFFLINE" else "MEDIUM"
    elif failure_rate_7d >= 0.05 and knowledge.default_risk == "LOW":
        risk = "MEDIUM"

    return ToolResult(
        ok=True,
        data={
            "risk_level": risk,
            "failure_rate_7d": failure_rate_7d,
            "batch_size": batch_size,
        },
    )


def should_require_hitl(
    risk_level: RiskLevel,
    recommended_action: str,
    batch_size: int,
) -> ToolResult:
    high_risk_words = ("阻止升级", "人工确认", "人工排查", "不允许全量", "禁止直接重试")
    require_hitl = (
        risk_level == "HIGH"
        or batch_size > 100
        or any(word in recommended_action for word in high_risk_words)
    )
    return ToolResult(ok=True, data={"require_hitl": require_hitl})


TOOL_REGISTRY: dict[str, ToolFunction] = {
    "query_device_status": query_device_status,
    "lookup_error_knowledge": lookup_error_knowledge,
    "estimate_operation_risk": estimate_operation_risk,
    "should_require_hitl": should_require_hitl,
}


def call_tool(
    name: str,
    args: dict[str, Any],
    registry: dict[str, ToolFunction] | None = None,
) -> ToolResult:
    tools = registry or TOOL_REGISTRY
    tool = tools.get(name)
    if tool is None:
        return ToolResult(ok=False, error="TOOL_NOT_ALLOWED")

    try:
        return tool(**args)
    except Exception as error:  # noqa: BLE001
        # 工具异常必须变成 Observation，不能让 Agent 进程直接崩溃。
        return ToolResult(ok=False, error=f"TOOL_ERROR:{type(error).__name__}:{error}")
