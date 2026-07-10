from __future__ import annotations

from app.agent.fallback_policy import retrieve_tms_context
from app.agent.tms_agent import (
    DeviceIssueQuery,
    DiagnosisResult,
    GateCase,
    GateCaseOutcome,
    GateMetrics,
    ReactTraceStep,
    run_react_loop,
)


def diagnose_issue(issue: DeviceIssueQuery) -> DiagnosisResult:
    """Day6 主编排入口：Query -> RAG -> ReAct -> Tool -> Result。

    这个函数只负责串联，不把 Hybrid、工具细节或报告逻辑塞进来，
    避免 Day6 变成不可解释的大函数。
    """

    if _is_cross_domain_query(issue):
        return _reject_cross_domain(issue)

    retrieval = retrieve_tms_context(
        issue.query,
        error_code=issue.error_code,
        top_k=3,
        force_empty=issue.force_rag_empty,
        force_reranker_failure=issue.force_reranker_failure,
        force_hybrid_failure=issue.force_hybrid_failure,
    )
    return run_react_loop(issue, retrieval)


def build_gate_cases() -> list[GateCase]:
    """构造 10 条固定通关样例，Demo 和 pytest 共用。"""

    return [
        GateCase(
            case_id="case_01",
            name="OTA_TIMEOUT Android 11 灰度重试",
            issue=DeviceIssueQuery(
                case_id="case_01",
                query="TMS-GD-ONLINE Android 11 设备 OTA_TIMEOUT 下载超时，是否可以灰度重试？",
                device_id="TMS-GD-ONLINE",
                error_code="OTA_TIMEOUT",
                failure_rate_7d=0.04,
                region="华南",
                android_version="11",
            ),
            expected_chunk_id="tms_e1002",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=False,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_02",
            name="DEVICE_OFFLINE 不直接 OTA",
            issue=DeviceIssueQuery(
                case_id="case_02",
                query="设备 TMS-GD-001 当前 DEVICE_OFFLINE，是否可以直接下发 OTA？",
                device_id="TMS-GD-001",
                error_code="DEVICE_OFFLINE",
                failure_rate_7d=0.02,
                region="华南",
                android_version="11",
            ),
            expected_chunk_id="tms_e1001",
            expected_actions=("query_device_status", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=True,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_03",
            name="FIRMWARE_MISMATCH 阻止升级",
            issue=DeviceIssueQuery(
                case_id="case_03",
                query="TMS-FW-003 出现 FIRMWARE_MISMATCH，Android 10 是否继续升级？",
                device_id="TMS-FW-003",
                error_code="FIRMWARE_MISMATCH",
                failure_rate_7d=0.01,
                region="华南",
                android_version="10",
            ),
            expected_chunk_id="tms_e1003",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=True,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_04",
            name="HIGH_FAILURE_RATE 华南先试点",
            issue=DeviceIssueQuery(
                case_id="case_04",
                query="华南区域 Android 11 近 7 天 HIGH_FAILURE_RATE=18%，是否可以全量升级？",
                device_id="TMS-RISK-004",
                error_code="HIGH_FAILURE_RATE",
                failure_rate_7d=0.18,
                region="华南",
                android_version="11",
                batch_size=100,
            ),
            expected_chunk_id="tms_e1004",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=True,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_05",
            name="SCRIPT_EXEC_ERROR 沙箱复现",
            issue=DeviceIssueQuery(
                case_id="case_05",
                query="远程脚本返回 SCRIPT_EXEC_ERROR，是否可以在生产设备直接重试？",
                device_id="TMS-SCRIPT-005",
                error_code="SCRIPT_EXEC_ERROR",
                failure_rate_7d=0.03,
                region="华东",
                android_version="11",
            ),
            expected_chunk_id="tms_e1005",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=True,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_06",
            name="UNKNOWN_CODE 不胡编",
            issue=DeviceIssueQuery(
                case_id="case_06",
                query="设备出现 UNKNOWN_CODE_X9，日志没有匹配手册，如何处理？",
                device_id="TMS-UNKNOWN-006",
                error_code="UNKNOWN_CODE_X9",
                failure_rate_7d=0.01,
                region="华南",
                android_version="11",
            ),
            expected_chunk_id=None,
            expected_actions=("query_device_status",),
            expect_hitl=True,
            expect_status="degraded",
            expect_fallback=True,
        ),
        GateCase(
            case_id="case_07",
            name="OTA_TIMEOUT RAG 无结果降级",
            issue=DeviceIssueQuery(
                case_id="case_07",
                query="TMS-RAG-007 出现 OTA_TIMEOUT，但模拟 RAG 无结果，是否仍能给出保守建议？",
                device_id="TMS-RAG-007",
                error_code="OTA_TIMEOUT",
                failure_rate_7d=0.04,
                region="华南",
                android_version="11",
                force_rag_empty=True,
            ),
            expected_chunk_id="tms_e1002",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=False,
            expect_status="degraded",
            expect_fallback=True,
        ),
        GateCase(
            case_id="case_08",
            name="设备工具异常转 Observation",
            issue=DeviceIssueQuery(
                case_id="case_08",
                query="TMS-TOOL-ERR 出现 OTA_TIMEOUT，同时模拟设备状态工具异常。",
                device_id="TMS-TOOL-ERR",
                error_code="OTA_TIMEOUT",
                failure_rate_7d=0.04,
                region="华南",
                android_version="11",
                force_tool_error=True,
            ),
            expected_chunk_id="tms_e1002",
            expected_actions=("query_device_status",),
            expect_hitl=True,
            expect_status="degraded",
            expect_fallback=True,
        ),
        GateCase(
            case_id="case_09",
            name="batch_size=500 必须 HITL",
            issue=DeviceIssueQuery(
                case_id="case_09",
                query="TMS-BATCH-009 OTA_TIMEOUT，计划 batch_size=500，是否可以自动批量升级？",
                device_id="TMS-BATCH-009",
                error_code="OTA_TIMEOUT",
                failure_rate_7d=0.06,
                region="华南",
                android_version="11",
                batch_size=500,
            ),
            expected_chunk_id="tms_e1002",
            expected_actions=("query_device_status", "query_ota_history", "estimate_batch_risk", "should_require_hitl"),
            expect_hitl=True,
            expect_status="ok",
        ),
        GateCase(
            case_id="case_10",
            name="直播卡顿误入 TMS 拒绝",
            issue=DeviceIssueQuery(
                case_id="case_10",
                query="OTT 直播卡顿，播放器首帧慢，是否是 TMS OTA 问题？",
                device_id="OTT-PLAYER-010",
                error_code=None,
                failure_rate_7d=0.0,
                region="华南",
                android_version="11",
            ),
            expected_chunk_id=None,
            expected_actions=(),
            expect_hitl=False,
            expect_status="rejected",
            expect_fallback=True,
        ),
    ]


def run_gate_cases(cases: list[GateCase] | None = None) -> list[GateCaseOutcome]:
    """逐条运行通关样例，单条异常不影响整体裁定。"""

    outcomes: list[GateCaseOutcome] = []
    for case in cases or build_gate_cases():
        try:
            result = diagnose_issue(case.issue)
            outcomes.append(GateCaseOutcome(case=case, result=result, crashed=False))
        except Exception as error:  # noqa: BLE001
            outcomes.append(
                GateCaseOutcome(
                    case=case,
                    result=None,
                    crashed=True,
                    error=f"{type(error).__name__}:{error}",
                )
            )
    return outcomes


def calculate_metrics(outcomes: list[GateCaseOutcome]) -> GateMetrics:
    """按 Day6 计划定义计算真实通关指标。"""

    total = len(outcomes)
    if total == 0:
        raise ValueError("outcomes must not be empty")

    structured = sum(1 for item in outcomes if item.result is not None)
    no_crash = sum(1 for item in outcomes if not item.crashed)
    rag_cases = [item for item in outcomes if item.case.expected_chunk_id is not None and item.result is not None]
    rag_hits = sum(
        1
        for item in rag_cases
        if item.result is not None and item.case.expected_chunk_id in {ref.chunk_id for ref in item.result.rag_references}
    )
    tool_cases = [item for item in outcomes if item.result is not None]
    tool_correct = sum(1 for item in tool_cases if _actions_match(item))
    hitl_cases = [item for item in outcomes if item.result is not None]
    hitl_correct = sum(1 for item in hitl_cases if item.result is not None and item.result.require_hitl == item.case.expect_hitl)
    fallback_cases = [item for item in outcomes if item.case.expect_fallback and item.result is not None]
    fallback_correct = sum(1 for item in fallback_cases if _fallback_matches(item))
    explanation_complete = sum(1 for item in outcomes if _has_explanation(item))
    passed_cases = sum(1 for item in outcomes if _case_passed(item))

    return GateMetrics(
        total_cases=total,
        passed_cases=passed_cases,
        end_to_end_success_rate=structured / total,
        no_crash_rate=no_crash / total,
        rag_hit_rate_at_3=_safe_rate(rag_hits, len(rag_cases)),
        tool_call_accuracy=_safe_rate(tool_correct, len(tool_cases)),
        hitl_trigger_accuracy=_safe_rate(hitl_correct, len(hitl_cases)),
        fallback_correctness=_safe_rate(fallback_correct, len(fallback_cases)),
        explanation_completeness=explanation_complete / total,
    )


def _is_cross_domain_query(issue: DeviceIssueQuery) -> bool:
    """前置领域判断，防止 OTT 问题污染 TMS 诊断。"""

    text = issue.query.lower()
    ott_terms = ("直播", "卡顿", "播放器", "首帧", "ott")
    return issue.error_code is None and any(term in text for term in ott_terms)


def _reject_cross_domain(issue: DeviceIssueQuery) -> DiagnosisResult:
    """跨域输入返回结构化拒绝结果，而不是硬套 TMS 结论。"""

    trace = [
        ReactTraceStep(
            step=0,
            thought="输入命中 OTT 播放体验词，Day6 不做 OTT 业务处理",
            action="domain_guard",
            observation="REJECTED_CROSS_DOMAIN_QUERY",
        )
    ]
    return DiagnosisResult(
        device_id=issue.device_id,
        error_code=issue.error_code,
        root_cause="非 TMS 运维异常，拒绝污染 TMS 诊断",
        evidence=["domain_guard -> REJECTED_CROSS_DOMAIN_QUERY"],
        rag_references=[],
        tool_observations=[],
        risk_level="LOW",
        require_hitl=False,
        recommended_actions=["路由到 OTT 运营/播放体验排查链路，Day6 不展开处理"],
        fallback_path="REJECTED",
        react_trace=trace,
        status="rejected",
        fallback_reason="CROSS_DOMAIN_QUERY",
    )


def _actions_match(outcome: GateCaseOutcome) -> bool:
    """校验实际工具调用是否覆盖样例预期。"""

    result = outcome.result
    if result is None:
        return False
    actual_actions = [step.action for step in result.react_trace if step.action not in {"observe_rag_context"}]
    return all(action in actual_actions for action in outcome.case.expected_actions)


def _fallback_matches(outcome: GateCaseOutcome) -> bool:
    """校验失败注入样例是否显式降级，而不是静默成功。"""

    result = outcome.result
    if result is None:
        return False
    return (
        result.status in {"degraded", "rejected"}
        or result.fallback_path not in {"L1", "L2", "L3"}
        or result.fallback_reason is not None
    )


def _has_explanation(outcome: GateCaseOutcome) -> bool:
    """校验结果是否保留可解释 trace 和 evidence。"""

    result = outcome.result
    if result is None:
        return False
    return bool(result.react_trace) and all(
        step.thought and step.action and step.observation
        for step in result.react_trace
    )


def _case_passed(outcome: GateCaseOutcome) -> bool:
    """单条样例是否达到预期，用于通关样例通过数。"""

    result = outcome.result
    if outcome.crashed or result is None:
        return False
    status_ok = result.status == outcome.case.expect_status
    if outcome.case.expect_status == "ok":
        status_ok = result.status in {"ok", "degraded"} and not outcome.case.expect_fallback
    rag_ok = True
    if outcome.case.expected_chunk_id is not None:
        rag_ok = outcome.case.expected_chunk_id in {ref.chunk_id for ref in result.rag_references}
    return (
        status_ok
        and rag_ok
        and _actions_match(outcome)
        and result.require_hitl == outcome.case.expect_hitl
        and _has_explanation(outcome)
    )


def _safe_rate(numerator: int, denominator: int) -> float:
    """避免没有分母的指标出现除零错误。"""

    if denominator == 0:
        return 1.0
    return numerator / denominator
