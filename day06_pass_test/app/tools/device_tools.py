from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agent.tms_agent import RiskLevel


@dataclass(frozen=True)
class ToolResult:
    """所有 Mock 工具的统一返回结构。

    统一结构可以让工具成功和失败都进入 ReAct Observation，避免某个
    工具抛异常后直接打断通关链路。
    """

    ok: bool
    tool_name: str
    data: dict[str, Any] | None = None
    error: str | None = None


ToolFunction = Callable[..., ToolResult]


DEVICE_STATUS: dict[str, dict[str, Any]] = {
    "TMS-GD-001": {
        "online": False,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.1",
        "last_seen": "2026-06-17T08:30:00+08:00",
    },
    "TMS-GD-ONLINE": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.3",
        "last_seen": "2026-07-09T10:10:00+08:00",
    },
    "TMS-FW-003": {
        "online": True,
        "region": "华南",
        "android_version": "10",
        "firmware_version": "1.9.8",
        "last_seen": "2026-07-09T10:20:00+08:00",
    },
    "TMS-RISK-004": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.2",
        "last_seen": "2026-07-09T10:25:00+08:00",
    },
    "TMS-SCRIPT-005": {
        "online": True,
        "region": "华东",
        "android_version": "11",
        "firmware_version": "2.4.0",
        "last_seen": "2026-07-09T10:30:00+08:00",
    },
    "TMS-UNKNOWN-006": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.3",
        "last_seen": "2026-07-09T10:35:00+08:00",
    },
    "TMS-RAG-007": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.3",
        "last_seen": "2026-07-09T10:40:00+08:00",
    },
    "TMS-TOOL-ERR": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.3",
        "last_seen": "2026-07-09T10:45:00+08:00",
    },
    "TMS-BATCH-009": {
        "online": True,
        "region": "华南",
        "android_version": "11",
        "firmware_version": "2.4.3",
        "last_seen": "2026-07-09T10:50:00+08:00",
    },
}


OTA_HISTORY: dict[str, dict[str, Any]] = {
    "TMS-GD-001": {"last_result": "FAILED", "last_error": "OTA_TIMEOUT", "failure_count_7d": 4},
    "TMS-GD-ONLINE": {"last_result": "FAILED", "last_error": "OTA_TIMEOUT", "failure_count_7d": 2},
    "TMS-FW-003": {"last_result": "BLOCKED", "last_error": "FIRMWARE_MISMATCH", "failure_count_7d": 1},
    "TMS-RISK-004": {"last_result": "FAILED", "last_error": "HIGH_FAILURE_RATE", "failure_count_7d": 18},
    "TMS-SCRIPT-005": {"last_result": "FAILED", "last_error": "SCRIPT_EXEC_ERROR", "failure_count_7d": 3},
    "TMS-RAG-007": {"last_result": "FAILED", "last_error": "OTA_TIMEOUT", "failure_count_7d": 2},
    "TMS-BATCH-009": {"last_result": "FAILED", "last_error": "OTA_TIMEOUT", "failure_count_7d": 5},
}


HIGH_RISK_ERROR_CODES = {"FIRMWARE_MISMATCH", "HIGH_FAILURE_RATE", "SCRIPT_EXEC_ERROR"}


def query_device_status(device_id: str, *, force_error: bool = False) -> ToolResult:
    """查询设备在线状态；Day6 只查 Mock 数据，不触碰真实设备。"""

    if force_error:
        raise RuntimeError("simulated device status failure")
    data = DEVICE_STATUS.get(device_id)
    if data is None:
        return ToolResult(
            ok=True,
            tool_name="query_device_status",
            data={"found": False, "device_id": device_id},
        )
    return ToolResult(
        ok=True,
        tool_name="query_device_status",
        data={"found": True, "device_id": device_id, **data},
    )


def query_ota_history(device_id: str, *, force_error: bool = False) -> ToolResult:
    """查询最近 OTA 历史，用来补足 RAG 之外的运行时证据。"""

    if force_error:
        raise RuntimeError("simulated ota history failure")
    data = OTA_HISTORY.get(device_id)
    if data is None:
        return ToolResult(
            ok=True,
            tool_name="query_ota_history",
            data={"found": False, "device_id": device_id},
        )
    return ToolResult(
        ok=True,
        tool_name="query_ota_history",
        data={"found": True, "device_id": device_id, **data},
    )


def estimate_batch_risk(
    region: str,
    android_version: str,
    failure_rate_7d: float,
    error_code: str | None,
    batch_size: int,
) -> ToolResult:
    """根据失败率、异常码和批量规模给出最小风险判断。"""

    risk: RiskLevel = "LOW"
    reasons: list[str] = []
    if error_code in HIGH_RISK_ERROR_CODES:
        risk = "HIGH"
        reasons.append(f"{error_code} 属于高风险异常")
    elif error_code in {"OTA_TIMEOUT", "DEVICE_OFFLINE"}:
        risk = "MEDIUM"
        reasons.append(f"{error_code} 默认至少 MEDIUM")

    if failure_rate_7d >= 0.10:
        risk = "HIGH"
        reasons.append("近 7 天失败率超过 10%")
    elif failure_rate_7d >= 0.05 and risk == "LOW":
        risk = "MEDIUM"
        reasons.append("近 7 天失败率超过 5%")

    if batch_size > 100:
        risk = "HIGH"
        reasons.append("批量规模超过 100 台")

    return ToolResult(
        ok=True,
        tool_name="estimate_batch_risk",
        data={
            "risk_level": risk,
            "region": region,
            "android_version": android_version,
            "failure_rate_7d": failure_rate_7d,
            "batch_size": batch_size,
            "reasons": reasons or ["未命中高风险规则"],
        },
    )


def should_require_hitl(
    risk_level: RiskLevel,
    batch_size: int,
    recommended_action: str,
) -> ToolResult:
    """把 HITL 作为硬门禁，防止高风险动作被自动执行。"""

    high_risk_words = ("阻止", "禁止", "人工", "暂缓", "不允许全量", "沙箱")
    require_hitl = (
        risk_level == "HIGH"
        or batch_size > 100
        or any(word in recommended_action for word in high_risk_words)
    )
    return ToolResult(
        ok=True,
        tool_name="should_require_hitl",
        data={"require_hitl": require_hitl},
    )


TOOL_REGISTRY: dict[str, ToolFunction] = {
    "query_device_status": query_device_status,
    "query_ota_history": query_ota_history,
    "estimate_batch_risk": estimate_batch_risk,
    "should_require_hitl": should_require_hitl,
}


def call_tool(
    name: str,
    args: dict[str, Any],
    registry: dict[str, ToolFunction] | None = None,
) -> ToolResult:
    """通过白名单调用工具，并把异常包装成 ToolResult。"""

    tools = registry or TOOL_REGISTRY
    tool = tools.get(name)
    if tool is None:
        return ToolResult(ok=False, tool_name=name, error="TOOL_NOT_ALLOWED")

    try:
        return tool(**args)
    except Exception as error:  # noqa: BLE001
        return ToolResult(
            ok=False,
            tool_name=name,
            error=f"TOOL_ERROR:{type(error).__name__}:{error}",
        )

