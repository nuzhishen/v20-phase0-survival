from decimal import Decimal

import pytest

from app.core.exceptions import BudgetExceededError, TruncationError
from app.core.llm_provider import (
    MockProvider,
    ProviderFactory,
    ProviderNotFoundError,
)
from app.core.token_budget import TokenBudget, TokenLedger
from app.schemas.llm import ChatMessage, LLMRequest, LLMResponse, TokenUsage


def make_request(estimated_cost: str = "0.5") -> LLMRequest:
    return LLMRequest(
        request_id="req-001",
        model_name="deepseek",
        messages=[ChatMessage(role="user", content="诊断设备 E1001")],
        temperature=0.1,
        top_p=0.1,
        max_tokens=300,
        task_type="tms_diagnosis",
        estimated_cost_cents=Decimal(estimated_cost),
    )


def make_response(finish_reason: str = "stop") -> LLMResponse:
    return LLMResponse(
        request_id="req-001",
        model_name="deepseek",
        content='{"diagnosis":"network timeout"}',
        usage=TokenUsage(
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            cost_cents=Decimal("0.4"),
        ),
        finish_reason=finish_reason,
        latency_ms=120,
        compliant=True,
    )


def test_factory_returns_registered_provider() -> None:
    provider = MockProvider(
        make_response(),
        TokenBudget(Decimal("10")),
        TokenLedger(),
    )
    factory = ProviderFactory()
    factory.register("deepseek", provider)

    assert factory.get("deepseek") is provider


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ProviderNotFoundError):
        ProviderFactory().get("unknown")


def test_successful_mock_call_charges_budget_and_records_ledger() -> None:
    budget = TokenBudget(Decimal("10"))
    ledger = TokenLedger()
    provider = MockProvider(make_response(), budget, ledger)

    response = provider.chat_completion(make_request())

    assert response.finish_reason == "stop"
    assert provider.call_count == 1
    assert budget.spent_cents == Decimal("0.4")
    assert ledger.total_cost_cents == Decimal("0.4")
    assert len(ledger.entries) == 1


def test_budget_is_checked_before_provider_call() -> None:
    # 预算被拦截时，MockProvider.call_count 必须保持 0。
    budget = TokenBudget(Decimal("1"), spent_cents=Decimal("0.5"))
    provider = MockProvider(make_response(), budget, TokenLedger())

    with pytest.raises(BudgetExceededError):
        provider.chat_completion(make_request("0.5"))

    assert provider.call_count == 0


def test_length_is_rejected_before_charge_and_ledger() -> None:
    # 截断响应不能进入扣费后的业务 Ledger；真实 Provider 可另记失败账单。
    budget = TokenBudget(Decimal("10"))
    ledger = TokenLedger()
    provider = MockProvider(make_response("length"), budget, ledger)

    with pytest.raises(TruncationError):
        provider.chat_completion(make_request())

    assert budget.spent_cents == 0
    assert ledger.entries == []

