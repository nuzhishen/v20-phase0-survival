import pytest

from app.react_loop import run_react_loop
from app.tools import call_tool


def test_known_error_code_normal_path() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
    )

    assert result.root_cause == "OTA 下载或安装超时"
    assert "灰度重试" in result.recommended_action
    assert result.risk_level in {"MEDIUM", "HIGH"}


def test_unknown_error_code_fallback_does_not_hallucinate() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="UNKNOWN_CODE",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
    )

    assert result.fallback_reason == "UNKNOWN_ERROR_CODE_REQUIRE_MANUAL_CHECK"
    assert result.root_cause == "未知异常码，禁止编造根因"
    assert result.require_hitl is True


def test_failure_rate_zero_is_not_high_risk_for_medium_error() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.0,
        region="华南",
        android_version="12",
    )

    assert result.risk_level in {"LOW", "MEDIUM"}
    assert result.risk_level != "HIGH"


def test_failure_rate_one_is_high_risk_and_hitl() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=1.0,
        region="华南",
        android_version="12",
    )

    assert result.risk_level == "HIGH"
    assert result.require_hitl is True


def test_empty_device_status_becomes_observation_not_crash() -> None:
    result = run_react_loop(
        device_id="TMS-NOT-FOUND",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
    )

    assert result.fallback_reason == "DEVICE_STATUS_EMPTY_RESULT"
    assert any("EMPTY_RESULT" in item for item in result.evidence)
    assert result.root_cause == "OTA 下载或安装超时"


@pytest.mark.parametrize(
    ("error_code", "expected_text", "expected_hitl"),
    [
        ("DEVICE_OFFLINE", "暂缓 OTA", False),
        ("FIRMWARE_MISMATCH", "阻止升级", True),
        ("HIGH_FAILURE_RATE", "不允许全量", True),
        ("SCRIPT_EXEC_ERROR", "沙箱复现", True),
    ],
)
def test_core_tms_error_scenarios(
    error_code: str,
    expected_text: str,
    expected_hitl: bool,
) -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code=error_code,
        failure_rate_7d=0.02,
        region="华南",
        android_version="12",
    )

    assert expected_text in result.recommended_action
    assert result.require_hitl is expected_hitl


def test_ota_timeout_offline_device_pauses_remote_operation() -> None:
    result = run_react_loop(
        device_id="TMS-GD-001",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="11",
    )

    assert "暂缓远程 OTA" in result.recommended_action
    assert any("'online': False" in item for item in result.evidence)


def test_batch_size_over_100_requires_hitl() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
        batch_size=500,
    )

    assert result.risk_level == "HIGH"
    assert result.require_hitl is True
    assert "HITL" in result.recommended_action


def test_tool_exception_is_converted_to_observation() -> None:
    def broken_query_device_status(device_id: str):  # type: ignore[no-untyped-def]
        raise RuntimeError(f"device service down: {device_id}")

    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
        registry={"query_device_status": broken_query_device_status},
    )

    assert result.fallback_reason == "query_device_status_TOOL_ERROR"
    assert result.require_hitl is True
    assert any("TOOL_ERROR" in item for item in result.evidence)


def test_illegal_tool_name_is_rejected() -> None:
    result = call_tool("delete_device", {"device_id": "TMS-GD-002"})

    assert result.ok is False
    assert result.error == "TOOL_NOT_ALLOWED"


def test_max_steps_guard_returns_safe_fallback() -> None:
    result = run_react_loop(
        device_id="TMS-GD-002",
        error_code="OTA_TIMEOUT",
        failure_rate_7d=0.08,
        region="华南",
        android_version="12",
        max_steps=1,
    )

    assert result.fallback_reason == "MAX_STEPS_EXCEEDED"
    assert result.require_hitl is True
