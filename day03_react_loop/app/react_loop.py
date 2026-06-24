from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from app.knowledge_base import UNKNOWN_ERROR_FALLBACK
from app.react_types import DiagnosisResult, ReactState, RiskLevel, ToolCall, ToolResult
from app.tools import TOOL_REGISTRY, ToolFunction, call_tool


MAX_STEPS = 6


def _record_action(state: ReactState, action: ToolCall) -> None:
    state.actions.append(f"{action.name}:{json.dumps(action.args, ensure_ascii=False, sort_keys=True)}")


def _repeated_action_detected(state: ReactState) -> bool:
    if len(state.actions) < 2:
        return False
    return state.actions[-1] == state.actions[-2]


def _observe_tool_result(state: ReactState, action: ToolCall, result: ToolResult) -> None:
    if not result.ok:
        state.observations.append(f"{action.name} -> ERROR:{result.error}")
        return

    data = result.data or {}
    if data.get("found") is False:
        state.observations.append(f"{action.name} -> EMPTY_RESULT:{data}")
        return

    state.observations.append(f"{action.name} -> OK:{data}")


def _finalize(
    state: ReactState,
    *,
    root_cause: str,
    recommended_action: str,
    risk_level: RiskLevel,
    require_hitl: bool,
    fallback_reason: str | None = None,
) -> DiagnosisResult:
    return DiagnosisResult(
        device_id=state.device_id,
        error_code=state.error_code,
        root_cause=root_cause,
        evidence=list(state.observations),
        recommended_action=recommended_action,
        risk_level=risk_level,
        require_hitl=require_hitl,
        fallback_reason=fallback_reason,
    )


def _safe_tool_failure_result(state: ReactState, action: ToolCall) -> DiagnosisResult:
    return _finalize(
        state,
        root_cause="工具调用失败，无法形成可靠诊断",
        recommended_action="停止自动处置，转人工排查",
        risk_level="HIGH",
        require_hitl=True,
        fallback_reason=f"{action.name}_TOOL_ERROR",
    )


def run_react_loop(
    *,
    device_id: str,
    error_code: str,
    failure_rate_7d: float,
    region: str,
    android_version: str,
    batch_size: int = 1,
    max_steps: int = MAX_STEPS,
    registry: dict[str, ToolFunction] | None = None,
) -> DiagnosisResult:
    """规则版最小 ReAct 状态机。

    这里故意不用 LLM Thought 生成，也不用 LangGraph。Day 3 的目标是把
    Action 选择、工具白名单、停止条件和 HITL 判断写成可测试的确定性逻辑。
    """

    state = ReactState(
        device_id=device_id,
        error_code=error_code,
        failure_rate_7d=failure_rate_7d,
        region=region,
        android_version=android_version,
        batch_size=batch_size,
    )

    device_status: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None
    risk_level: RiskLevel | None = None
    require_hitl: bool | None = None
    fallback_reason: str | None = None

    while state.step < max_steps:
        state.step += 1

        if device_status is None:
            action = ToolCall("query_device_status", {"device_id": state.device_id})
        elif knowledge is None:
            action = ToolCall("lookup_error_knowledge", {"error_code": state.error_code})
        elif risk_level is None:
            action = ToolCall(
                "estimate_operation_risk",
                {
                    "failure_rate_7d": state.failure_rate_7d,
                    "error_code": state.error_code,
                    "batch_size": state.batch_size,
                },
            )
        elif require_hitl is None:
            action = ToolCall(
                "should_require_hitl",
                {
                    "risk_level": risk_level,
                    "recommended_action": _recommended_action_for(
                        state,
                        device_status,
                        knowledge,
                    ),
                    "batch_size": state.batch_size,
                },
            )
        else:
            return _finalize(
                state,
                root_cause=_root_cause_for(knowledge),
                recommended_action=_recommended_action_for(state, device_status, knowledge),
                risk_level=risk_level,
                require_hitl=require_hitl,
                fallback_reason=fallback_reason,
            )

        _record_action(state, action)
        if _repeated_action_detected(state):
            # 同一 Action 连续重复说明状态机没有取得新信息，立即安全终止。
            state.observations.append(f"{action.name} -> REPEATED_ACTION_STOP")
            return _finalize(
                state,
                root_cause="重复工具调用，状态机未取得新信息",
                recommended_action="停止自动处置，转人工排查",
                risk_level="HIGH",
                require_hitl=True,
                fallback_reason="REPEATED_ACTION_STOP",
            )

        result = call_tool(action.name, action.args, registry)
        _observe_tool_result(state, action, result)
        if not result.ok:
            return _safe_tool_failure_result(state, action)

        data = result.data or {}
        if action.name == "query_device_status":
            device_status = data
            if data.get("found") is False:
                fallback_reason = "DEVICE_STATUS_EMPTY_RESULT"
        elif action.name == "lookup_error_knowledge":
            knowledge = data
            if data.get("found") is False:
                return _finalize(
                    state,
                    root_cause="未知异常码，禁止编造根因",
                    recommended_action="转人工排查，补充异常码知识后再自动化处理",
                    risk_level="HIGH",
                    require_hitl=True,
                    fallback_reason=UNKNOWN_ERROR_FALLBACK,
                )
        elif action.name == "estimate_operation_risk":
            risk_level = data["risk_level"]
        elif action.name == "should_require_hitl":
            require_hitl = bool(data["require_hitl"])

    # max_steps 是最后安全网，防止规则缺陷或未来 LLM 接入后无限循环。
    return _finalize(
        state,
        root_cause="超过最大 ReAct 步数，未形成可靠诊断",
        recommended_action="停止自动处置，转人工复核",
        risk_level="HIGH",
        require_hitl=True,
        fallback_reason="MAX_STEPS_EXCEEDED",
    )


def _root_cause_for(knowledge: dict[str, Any] | None) -> str:
    if not knowledge or knowledge.get("found") is False:
        return "未知异常码，禁止编造根因"
    return str(knowledge["root_cause"])


def _recommended_action_for(
    state: ReactState,
    device_status: dict[str, Any] | None,
    knowledge: dict[str, Any] | None,
) -> str:
    if device_status and device_status.get("found") is True and not device_status.get("online", True):
        return "设备离线，暂缓远程 OTA，转人工巡检"
    if not knowledge or knowledge.get("found") is False:
        return "转人工排查，补充异常码知识后再自动化处理"
    if state.batch_size > 100:
        return f"{knowledge['recommended_action']}；批量 {state.batch_size} 台需先 HITL 审批"
    return str(knowledge["recommended_action"])


def main() -> None:
    result = run_react_loop(
        device_id="TMS-GD-001",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.18,
        region="华南",
        android_version="11",
        batch_size=1,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
