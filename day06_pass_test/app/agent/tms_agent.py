from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
DiagnosisStatus = Literal["ok", "degraded", "rejected", "failed"]


@dataclass(frozen=True)
class DeviceIssueQuery:
    """承载 Day6 固定通关输入，避免把 FastAPI 引进主链路。

    Day6 的目标是验证 ReAct + RAG + Tool 闭环，不是验证 Web API。
    因此这里用轻量 dataclass 表达输入契约，保留必要的失败注入开关，
    方便 10 条样例和 pytest 复现同一条链路。
    """

    query: str
    device_id: str
    error_code: str | None = None
    failure_rate_7d: float = 0.0
    region: str = "华南"
    android_version: str = "11"
    batch_size: int = 1
    case_id: str = ""
    force_rag_empty: bool = False
    force_tool_error: bool = False
    force_reranker_failure: bool = False
    force_hybrid_failure: bool = False


@dataclass(frozen=True)
class RAGReference:
    """保留检索证据的来源、分数和文本，支撑可解释审计。

    面试追问时不能只说“RAG 查到了”，必须能指出命中的 chunk、
    来源文件、标题和降级层级。
    """

    chunk_id: str
    section: str
    title: str
    score: float
    text: str
    domain: str
    source: str
    level_used: str


@dataclass(frozen=True)
class RetrievalResult:
    """统一检索层输出，让 ReAct 不感知 Hybrid/Reranker 细节。

    这层是 Day6 的适配边界：上层只看 evidence、confidence 和
    fallback_path，具体是 L1 还是 L4 由检索层自己记录。
    """

    query: str
    level_used: str
    fallback_path: str
    low_confidence: bool
    confidence: float
    latency_ms: float
    references: list[RAGReference] = field(default_factory=list)
    fallback_reason: str | None = None


@dataclass(frozen=True)
class ToolObservation:
    """记录工具调用结果，保证工具失败也能进入 Observation。

    Agent Runtime 不能把工具异常当成进程异常；它应该成为状态机的
    观察结果，再由决策层安全收敛。
    """

    tool_name: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class ReactTraceStep:
    """记录 Thought / Action / Observation，证明每一步可解释。

    Day6 不接真实 LLM，但仍保留 ReAct 轨迹，目的是让通关结果可测、
    可审计，也方便晚间复盘口述。
    """

    step: int
    thought: str
    action: str
    observation: str


@dataclass(frozen=True)
class DiagnosisResult:
    """Day6 最终结构化结果，是通关测试的核心输出。

    这个结果把 RAG 引用、工具观察、风险、HITL 和 fallback 都显式
    落出来，避免只返回一段不可验证的自然语言建议。
    """

    device_id: str
    error_code: str | None
    root_cause: str
    evidence: list[str]
    rag_references: list[RAGReference]
    tool_observations: list[ToolObservation]
    risk_level: RiskLevel
    require_hitl: bool
    recommended_actions: list[str]
    fallback_path: str
    react_trace: list[ReactTraceStep]
    status: DiagnosisStatus
    fallback_reason: str | None = None

    @property
    def requires_hitl(self) -> bool:
        """兼容补充计划里的字段命名，避免报告和测试口径打架。"""

        return self.require_hitl

    def to_dict(self) -> dict[str, Any]:
        """把 dataclass 结果转换成可 JSON 序列化的审计字典。"""

        payload = asdict(self)
        payload["requires_hitl"] = self.require_hitl
        return payload


@dataclass(frozen=True)
class GateCase:
    """定义 10 条通关样例的预期，测试和 Demo 共享同一份靶子。

    样例预期集中放在这里，避免 Demo 通过而测试用另一套标准。
    """

    case_id: str
    name: str
    issue: DeviceIssueQuery
    expected_chunk_id: str | None
    expected_actions: tuple[str, ...]
    expect_hitl: bool
    expect_status: DiagnosisStatus
    expect_fallback: bool = False


@dataclass(frozen=True)
class GateCaseOutcome:
    """保存单条样例的运行结果和异常信息，用于真实指标计算。"""

    case: GateCase
    result: DiagnosisResult | None
    crashed: bool
    error: str | None = None


@dataclass(frozen=True)
class GateMetrics:
    """聚合 Day6 通关指标，保证报告数字来自同一套计算逻辑。"""

    total_cases: int
    passed_cases: int
    end_to_end_success_rate: float
    no_crash_rate: float
    rag_hit_rate_at_3: float
    tool_call_accuracy: float
    hitl_trigger_accuracy: float
    fallback_correctness: float
    explanation_completeness: float

    def to_percent_dict(self) -> dict[str, str]:
        """返回报告可直接使用的百分比字符串。"""

        return {
            "End-to-End Success Rate": _format_percent(self.end_to_end_success_rate),
            "No Crash Rate": _format_percent(self.no_crash_rate),
            "RAG Hit Rate@3": _format_percent(self.rag_hit_rate_at_3),
            "Tool Call Accuracy": _format_percent(self.tool_call_accuracy),
            "HITL Trigger Accuracy": _format_percent(self.hitl_trigger_accuracy),
            "Fallback Correctness": _format_percent(self.fallback_correctness),
            "Explanation Completeness": _format_percent(self.explanation_completeness),
        }


def _format_percent(value: float) -> str:
    """统一指标格式，避免报告里小数和百分比混用。"""

    return f"{value * 100:.2f}%"


def run_react_loop(
    issue: DeviceIssueQuery,
    retrieval: RetrievalResult,
    *,
    max_steps: int = 6,
) -> DiagnosisResult:
    """执行 Day3 风格的规则版 ReAct 状态机。

    这里故意不用 LangGraph 或真实 LLM。Day6 要验证的是 Agent Runtime
    的控制边界：工具白名单、Observation、HITL、fallback 和安全终止。
    """

    from app.agent.fallback_policy import get_error_knowledge, normalize_error_code
    from app.tools.device_tools import call_tool

    normalized_error = normalize_error_code(issue.error_code)
    trace: list[ReactTraceStep] = []
    observations: list[ToolObservation] = []
    actions: list[str] = []
    device_status: dict[str, Any] | None = None
    ota_history: dict[str, Any] | None = None
    risk_level: RiskLevel | None = None
    require_hitl: bool | None = None

    trace.append(
        ReactTraceStep(
            step=0,
            thought="先把 RAG TopK 作为初始证据，但不让它绕过工具和安全判断",
            action="observe_rag_context",
            observation=_rag_observation(retrieval),
        )
    )

    for step in range(1, max_steps + 1):
        if device_status is None:
            action = "query_device_status"
            args: dict[str, Any] = {
                "device_id": issue.device_id,
                "force_error": issue.force_tool_error,
            }
            thought = "需要先确认设备在线状态，离线设备不能直接 OTA"
        elif _should_query_ota_history(normalized_error) and ota_history is None:
            action = "query_ota_history"
            args = {"device_id": issue.device_id}
            thought = "需要查询最近 OTA 历史，验证异常是否和升级任务相关"
        elif risk_level is None:
            action = "estimate_batch_risk"
            args = {
                "region": issue.region,
                "android_version": issue.android_version,
                "failure_rate_7d": issue.failure_rate_7d,
                "error_code": normalized_error,
                "batch_size": issue.batch_size,
            }
            thought = "需要根据失败率、异常码和批量规模评估风险"
        elif require_hitl is None:
            action = "should_require_hitl"
            args = {
                "risk_level": risk_level,
                "batch_size": issue.batch_size,
                "recommended_action": _recommended_action(issue, retrieval, device_status),
            }
            thought = "需要把 HIGH 风险和大批量操作转成人工审批门禁"
        else:
            return _finalize_result(
                issue,
                retrieval,
                observations,
                trace,
                device_status,
                risk_level,
                require_hitl,
            )

        action_key = f"{action}:{_stable_args(args)}"
        actions.append(action_key)
        if len(actions) >= 2 and actions[-1] == actions[-2]:
            trace.append(
                ReactTraceStep(
                    step=step,
                    thought="检测到连续重复 Action，状态机未获得新信息",
                    action=action,
                    observation="REPEATED_ACTION_STOP",
                )
            )
            return _manual_stop_result(
                issue,
                retrieval,
                observations,
                trace,
                fallback_reason="REPEATED_ACTION_STOP",
            )

        tool_result = call_tool(action, args)
        observation = ToolObservation(
            tool_name=tool_result.tool_name,
            ok=tool_result.ok,
            data=tool_result.data,
            error=tool_result.error,
        )
        observations.append(observation)
        trace.append(
            ReactTraceStep(
                step=step,
                thought=thought,
                action=action,
                observation=_tool_observation_text(observation),
            )
        )

        if not tool_result.ok:
            return _manual_stop_result(
                issue,
                retrieval,
                observations,
                trace,
                fallback_reason=f"{action}_TOOL_ERROR",
            )

        data = tool_result.data or {}
        if action == "query_device_status":
            device_status = data
            if data.get("found") is False:
                return _manual_stop_result(
                    issue,
                    retrieval,
                    observations,
                    trace,
                    fallback_reason="DEVICE_STATUS_EMPTY_RESULT",
                )
        elif action == "query_ota_history":
            ota_history = data
        elif action == "estimate_batch_risk":
            risk_level = data["risk_level"]
        elif action == "should_require_hitl":
            require_hitl = bool(data["require_hitl"])

        knowledge = get_error_knowledge(normalized_error)
        if knowledge is None and device_status is not None:
            trace.append(
                ReactTraceStep(
                    step=step,
                    thought="异常码不在已知知识库，禁止编造根因",
                    action="final_unknown_error",
                    observation="UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK",
                )
            )
            return _manual_stop_result(
                issue,
                retrieval,
                observations,
                trace,
                fallback_reason="UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK",
            )

    trace.append(
        ReactTraceStep(
            step=max_steps + 1,
            thought="超过最大 ReAct 步数，触发最后安全网",
            action="max_steps_stop",
            observation="MAX_STEPS_EXCEEDED",
        )
    )
    return _manual_stop_result(
        issue,
        retrieval,
        observations,
        trace,
        fallback_reason="MAX_STEPS_EXCEEDED",
    )


def _finalize_result(
    issue: DeviceIssueQuery,
    retrieval: RetrievalResult,
    observations: list[ToolObservation],
    trace: list[ReactTraceStep],
    device_status: dict[str, Any] | None,
    risk_level: RiskLevel,
    require_hitl: bool,
) -> DiagnosisResult:
    """把 ReAct 状态收敛成结构化 DiagnosisResult。"""

    root_cause = _root_cause(issue, retrieval)
    recommended = _recommended_action(issue, retrieval, device_status)
    offline = bool(device_status and device_status.get("found") is True and not device_status.get("online", True))
    final_hitl = require_hitl or offline or issue.batch_size > 100 or risk_level == "HIGH"
    status: DiagnosisStatus = "degraded" if retrieval.fallback_path != "L1" or retrieval.low_confidence else "ok"
    fallback_reason = retrieval.fallback_reason
    if offline:
        fallback_reason = fallback_reason or "DEVICE_OFFLINE_REQUIRE_MANUAL_CHECK"
    return DiagnosisResult(
        device_id=issue.device_id,
        error_code=issue.error_code,
        root_cause=root_cause,
        evidence=_evidence_lines(retrieval, observations),
        rag_references=list(retrieval.references),
        tool_observations=list(observations),
        risk_level=risk_level,
        require_hitl=final_hitl,
        recommended_actions=[recommended],
        fallback_path=retrieval.fallback_path,
        react_trace=list(trace),
        status=status,
        fallback_reason=fallback_reason,
    )


def _manual_stop_result(
    issue: DeviceIssueQuery,
    retrieval: RetrievalResult,
    observations: list[ToolObservation],
    trace: list[ReactTraceStep],
    *,
    fallback_reason: str,
) -> DiagnosisResult:
    """安全终止分支，保证失败也返回结构化结果。"""

    return DiagnosisResult(
        device_id=issue.device_id,
        error_code=issue.error_code,
        root_cause=_root_cause(issue, retrieval, fallback_reason=fallback_reason),
        evidence=_evidence_lines(retrieval, observations),
        rag_references=list(retrieval.references),
        tool_observations=list(observations),
        risk_level="HIGH",
        require_hitl=True,
        recommended_actions=["停止自动处置，转人工排查，并补充缺失证据后再重试"],
        fallback_path=retrieval.fallback_path,
        react_trace=list(trace),
        status="degraded",
        fallback_reason=fallback_reason,
    )


def _root_cause(
    issue: DeviceIssueQuery,
    retrieval: RetrievalResult,
    *,
    fallback_reason: str | None = None,
) -> str:
    """优先使用已知异常码知识；未知码不编造根因。"""

    from app.agent.fallback_policy import get_error_knowledge

    if fallback_reason == "UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK":
        return "未知异常码，当前知识库没有可靠根因"
    knowledge = get_error_knowledge(issue.error_code)
    if knowledge is not None:
        return knowledge.root_cause
    if retrieval.references:
        return f"基于 RAG 证据推断：{retrieval.references[0].title}"
    return "证据不足，无法形成可靠根因"


def _recommended_action(
    issue: DeviceIssueQuery,
    retrieval: RetrievalResult,
    device_status: dict[str, Any] | None,
) -> str:
    """生成建议动作，设备离线和高风险优先覆盖普通建议。"""

    from app.agent.fallback_policy import get_error_knowledge

    if device_status and device_status.get("found") is True and not device_status.get("online", True):
        return "设备离线，暂缓远程 OTA 或脚本操作，先人工确认电源、网络和 EMQX 在线状态"
    knowledge = get_error_knowledge(issue.error_code)
    if knowledge is None:
        return "转人工排查，补充异常码知识后再进入自动化闭环"
    action = knowledge.recommended_action
    if issue.batch_size > 100:
        action = f"{action}；当前 batch_size={issue.batch_size}，必须 HITL 审批后才能继续"
    if retrieval.low_confidence:
        action = f"{action}；当前检索低置信，只能作为保守建议"
    return action


def _should_query_ota_history(error_code: str | None) -> bool:
    """仅对 OTA/脚本相关异常查询历史，避免无意义工具调用。"""

    return error_code in {"OTA_TIMEOUT", "FIRMWARE_MISMATCH", "HIGH_FAILURE_RATE", "SCRIPT_EXEC_ERROR"}


def _rag_observation(retrieval: RetrievalResult) -> str:
    """把 RAG TopK 压缩成一条可读 Observation。"""

    if not retrieval.references:
        return f"RAG_EMPTY level={retrieval.level_used} reason={retrieval.fallback_reason}"
    refs = ", ".join(f"{ref.chunk_id}:{ref.score:.2f}" for ref in retrieval.references)
    return f"RAG_TOPK level={retrieval.level_used} confidence={retrieval.confidence:.2f} refs={refs}"


def _tool_observation_text(observation: ToolObservation) -> str:
    """把工具返回转换成稳定文本，便于测试和报告复用。"""

    if observation.ok:
        return f"{observation.tool_name} -> OK:{observation.data}"
    return f"{observation.tool_name} -> ERROR:{observation.error}"


def _evidence_lines(
    retrieval: RetrievalResult,
    observations: list[ToolObservation],
) -> list[str]:
    """合并 RAG 引用和工具观察，形成最终 evidence 字段。"""

    lines = [
        f"RAG[{ref.level_used}] {ref.chunk_id} {ref.title} score={ref.score:.2f}"
        for ref in retrieval.references
    ]
    lines.extend(_tool_observation_text(item) for item in observations)
    if retrieval.fallback_reason:
        lines.append(f"fallback_reason={retrieval.fallback_reason}")
    return lines


def _stable_args(args: dict[str, Any]) -> str:
    """生成重复 Action 检测用的稳定参数字符串。"""

    return "|".join(f"{key}={args[key]}" for key in sorted(args))
