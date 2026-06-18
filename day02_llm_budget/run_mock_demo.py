from decimal import Decimal

from app.core.exceptions import BudgetExceededError, TruncationError
from app.core.llm_provider import MockProvider, ProviderFactory
from app.core.retry_policy import Failure, FailureKind, decide_retry
from app.core.token_budget import TokenBudget, TokenLedger
from app.schemas.llm import ChatMessage, LLMRequest, LLMResponse, TokenUsage


def build_request(estimated_cost_cents: str = "0.5") -> LLMRequest:
    # 演示请求只走 Mock，不调用真实模型； estimated_cost  用来触发预算预检。
    return LLMRequest(
        request_id="req-demo-001",
        model_name="deepseek",
        messages=[
            ChatMessage(
                role="user",
                content="Diagnose TMS device E1001 in south_china.",
            )
        ],
        temperature=0.1,
        top_p=0.1,
        max_tokens=300,
        task_type="tms_diagnosis",
        estimated_cost_cents=Decimal(estimated_cost_cents),
    )


def build_response(finish_reason: str = "stop") -> LLMResponse:
    # 模拟 Provider 的标准返回，usage 用于预算扣费和 Ledger 记录。
    return LLMResponse(
        request_id="req-demo-001",
        model_name="deepseek",
        content='{"diagnosis":"network timeout","risk_level":"medium"}',
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


def run_success_case() -> None:
    # 正常链路：Factory 路由 -> 预算预检 -> finish_reason 校验 -> 扣费 -> Ledger。
    budget = TokenBudget(limit_cents=Decimal("10"))
    ledger = TokenLedger()
    factory = ProviderFactory()
    factory.register(
        "deepseek",
        MockProvider(build_response(), budget, ledger),
    )

    response = factory.get("deepseek").chat_completion(build_request())

    print("[SUCCESS]")
    print(f"content: {response.content}")
    print(f"finish_reason: {response.finish_reason}")
    print(f"spent_cents: {budget.spent_cents}")
    print(f"ledger_entries: {len(ledger.entries)}")


def run_budget_case() -> None:
    # 预算刚好达到上限也要拦截，验证 Provider 不会真正执行。
    provider = MockProvider(
        build_response(),
        TokenBudget(limit_cents=Decimal("1"), spent_cents=Decimal("0.5")),
        TokenLedger(),
    )

    print("\n[BUDGET BLOCK]")
    try:
        provider.chat_completion(build_request("0.5"))
    except BudgetExceededError as error:
        print(f"blocked: {error}")
        print(f"provider_call_count: {provider.call_count}")


def run_truncation_case() -> None:
    # length 截断必须阻断，不能继续解析残缺 JSON。
    provider = MockProvider(
        build_response("length"),
        TokenBudget(limit_cents=Decimal("10")),
        TokenLedger(),
    )

    print("\n[TRUNCATION]")
    try:
        provider.chat_completion(build_request())
    except TruncationError as error:
        print(f"blocked: {error}")


def run_retry_cases() -> None:
    # 每次运行都会生成不同 jitter，符合生产中打散重试流量的目的。
    print("\n[RETRY POLICY WITH RANDOM JITTER]")
    for status_code in (429, 503, 400):
        decision = decide_retry(
            Failure(FailureKind.HTTP, status_code=status_code)
        )
        print(
            f"status={status_code}, retry={decision.should_retry}, "
            f"delays={decision.delays_seconds}"
        )



def main() -> None:
    print("=== Phase 0 Day 2 Mock LLM Demo ===")
    run_success_case()
    run_budget_case()
    run_truncation_case()
    run_retry_cases()


if __name__ == "__main__":
    main()
