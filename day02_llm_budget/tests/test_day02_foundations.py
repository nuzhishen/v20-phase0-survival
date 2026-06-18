from decimal import Decimal

import pytest

from app.core.exceptions import (
    BudgetExceededError,
    ContentFilteredError,
    ProtocolError,
    TruncationError,
)
from app.core.finish_reason import ResponseAction, classify_finish_reason
from app.core.parameter_routing import TaskType, parameters_for
from app.core.retry_policy import Failure, FailureKind, decide_retry
from app.core.token_economics import (
    ModelPrice,
    TokenBreakdown,
    estimate_cost,
    preflight_budget,
)


def test_required_token_distribution() -> None:
    usage = TokenBreakdown(500, 800, 200, 600, 300)

    assert usage.prompt_tokens == 2100
    assert usage.hidden_tokens == 1400
    assert usage.total_tokens == 2400


def test_preflight_blocks_before_budget_is_consumed() -> None:
    # 预算预检必须发生在真实 API 调用前，避免事后才发现成本超限。
    with pytest.raises(BudgetExceededError):
        preflight_budget(
            estimated_cost=Decimal("2"),
            spent=Decimal("97.5"),
            limit=Decimal("100"),
        )


def test_cost_separates_input_and_output_prices() -> None:
    usage = TokenBreakdown(500, 800, 200, 600, 300)
    price = ModelPrice(Decimal("1"), Decimal("2"))

    assert estimate_cost(usage, price) == Decimal("0.0027")


def test_finish_reason_stop_and_tool_calls_are_distinct_valid_states() -> None:
    # tool_calls 是正常 Agent 状态，不能误判为 length 截断。
    assert classify_finish_reason("stop") == ResponseAction.PARSE_CONTENT
    assert (
        classify_finish_reason("tool_calls", has_tool_calls=True)
        == ResponseAction.VALIDATE_TOOL_CALLS
    )


@pytest.mark.parametrize(
    ("reason", "error_type"),
    [
        ("length", TruncationError),
        ("content_filter", ContentFilteredError),
        (None, ProtocolError),
        ("unknown", ProtocolError),
    ],
)
def test_unsafe_finish_reasons_are_rejected(
    reason: str | None,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        classify_finish_reason(reason)


def test_tool_calls_without_payload_is_protocol_error() -> None:
    with pytest.raises(ProtocolError):
        classify_finish_reason("tool_calls", has_tool_calls=False)


@pytest.mark.parametrize(
    ("status_code", "expected", "attempts"),
    [
        (429, True, 3),
        (503, True, 2),
        (400, False, 0),
        (401, False, 0),
        (403, False, 0),
    ],
)
def test_http_retry_classification(
    status_code: int,
    expected: bool,
    attempts: int,
) -> None:
    decision = decide_retry(
        Failure(FailureKind.HTTP, status_code=status_code),
        jitter_source=lambda minimum, maximum: maximum,
    )

    assert decision.should_retry is expected
    assert len(decision.delays_seconds) == attempts


@pytest.mark.parametrize(
    ("status_code", "base_delays"),
    [
        (429, (1.0, 2.0, 4.0)),
        (503, (1.0, 2.0)),
    ],
)
def test_retry_jitter_stays_within_twenty_percent(
    status_code: int,
    base_delays: tuple[float, ...],
) -> None:
    decision = decide_retry(
        Failure(FailureKind.HTTP, status_code=status_code),
        jitter_source=lambda minimum, maximum: maximum,
    )

    for actual, base in zip(decision.delays_seconds, base_delays, strict=True):
        assert base <= actual <= base * 1.2
        assert actual == pytest.approx(base * 1.2)


def test_truncation_is_not_retried_identically() -> None:
    # length 原样重试仍会截断，必须走上下文压缩或 Fallback。
    decision = decide_retry(
        Failure(FailureKind.RUNTIME, error=TruncationError("truncated"))
    )

    assert decision.should_retry is False
    assert decision.fallback_required is True


def test_timeout_has_one_bounded_retry() -> None:
    decision = decide_retry(
        Failure(FailureKind.TIMEOUT),
        jitter_source=lambda minimum, maximum: maximum,
    )

    assert decision.should_retry is True
    assert len(decision.delays_seconds) == 1
    assert decision.delays_seconds[0] == pytest.approx(0.6)


def test_task_parameter_routes() -> None:
    assert parameters_for(TaskType.TMS_DIAGNOSIS).temperature == 0.1
    assert parameters_for(TaskType.ELDERLY_MEDICATION).temperature == 0.0
    assert parameters_for(TaskType.OTT_REPORT).top_p == 0.9

