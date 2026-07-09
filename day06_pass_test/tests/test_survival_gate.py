from __future__ import annotations

from app.agent.diagnosis_pipeline import build_gate_cases, calculate_metrics, diagnose_issue, run_gate_cases


def test_survival_gate_runs_ten_cases_without_crash() -> None:
    """通关测试必须覆盖 10 条样例，并保证无未捕获异常。"""

    outcomes = run_gate_cases()
    metrics = calculate_metrics(outcomes)

    assert metrics.total_cases == 10
    assert metrics.no_crash_rate == 1.0
    assert metrics.end_to_end_success_rate == 1.0
    assert metrics.passed_cases >= 8


def test_gate_metrics_meet_phase0_thresholds() -> None:
    """按计划中的通关线校验真实指标。"""

    metrics = calculate_metrics(run_gate_cases())

    assert metrics.rag_hit_rate_at_3 >= 0.70
    assert metrics.tool_call_accuracy >= 0.80
    assert metrics.hitl_trigger_accuracy >= 0.90
    assert metrics.fallback_correctness >= 0.80
    assert metrics.explanation_completeness == 1.0


def test_ota_timeout_hits_expected_rag_and_tools() -> None:
    """OTA_TIMEOUT 必须命中 OTA 知识，并调用设备状态与 OTA 历史工具。"""

    case = build_gate_cases()[0]
    result = diagnose_issue(case.issue)

    assert result.status == "ok"
    assert "tms_e1002" in {ref.chunk_id for ref in result.rag_references}
    actions = [step.action for step in result.react_trace]
    assert "query_device_status" in actions
    assert "query_ota_history" in actions
    assert "estimate_batch_risk" in actions
    assert result.require_hitl is False


def test_offline_device_pauses_ota_and_requires_hitl() -> None:
    """离线设备不能直接 OTA，必须进入人工确认。"""

    case = build_gate_cases()[1]
    result = diagnose_issue(case.issue)

    assert result.require_hitl is True
    assert any("暂缓远程 OTA" in action for action in result.recommended_actions)
    assert any(obs.tool_name == "query_device_status" and obs.ok for obs in result.tool_observations)


def test_unknown_error_code_does_not_fabricate_root_cause() -> None:
    """未知异常码必须转人工，不能编造根因。"""

    case = build_gate_cases()[5]
    result = diagnose_issue(case.issue)

    assert result.status == "degraded"
    assert result.require_hitl is True
    assert result.fallback_reason == "UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK"
    assert "未知异常码" in result.root_cause


def test_rag_empty_falls_back_to_rule_knowledge() -> None:
    """RAG 无结果时必须降级到 L4 硬编码知识库。"""

    case = build_gate_cases()[6]
    result = diagnose_issue(case.issue)

    assert result.status == "degraded"
    assert result.fallback_path == "L4"
    assert result.fallback_reason == "FORCED_RAG_EMPTY"
    assert "tms_e1002" in {ref.chunk_id for ref in result.rag_references}


def test_tool_error_becomes_observation_not_crash() -> None:
    """工具异常必须变成 Observation，并返回结构化降级结果。"""

    case = build_gate_cases()[7]
    result = diagnose_issue(case.issue)

    assert result.status == "degraded"
    assert result.require_hitl is True
    assert result.fallback_reason == "query_device_status_TOOL_ERROR"
    assert any(obs.tool_name == "query_device_status" and not obs.ok for obs in result.tool_observations)


def test_batch_size_500_requires_hitl() -> None:
    """大批量操作必须强制 HITL，不能自动全量升级。"""

    case = build_gate_cases()[8]
    result = diagnose_issue(case.issue)

    assert result.require_hitl is True
    assert result.risk_level == "HIGH"
    assert "tms_e1002" in {ref.chunk_id for ref in result.rag_references}


def test_ott_playback_query_is_rejected_from_tms_flow() -> None:
    """OTT 直播卡顿不能污染 TMS 诊断链路。"""

    case = build_gate_cases()[9]
    result = diagnose_issue(case.issue)

    assert result.status == "rejected"
    assert result.fallback_reason == "CROSS_DOMAIN_QUERY"
    assert result.rag_references == []
    assert result.tool_observations == []
    assert [step.action for step in result.react_trace] == ["domain_guard"]

