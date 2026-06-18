from abc import ABC, abstractmethod

from app.core.finish_reason import classify_finish_reason
from app.core.token_budget import TokenBudget, TokenLedger
from app.schemas.llm import LLMRequest, LLMResponse


class ProviderNotFoundError(LookupError):
    "模型名称未注册时抛出，防止静默落到错误 Provider。"

    pass


class LLMProvider(ABC):
    "统一 LLM Provider 接口，屏蔽 DeepSeek/Qwen/Mock 等实现差异。"

    @abstractmethod
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class MockProvider(LLMProvider):
    def __init__(
        self,
        response: LLMResponse,
        budget: TokenBudget,
        ledger: TokenLedger,
    ) -> None:
        self.response = response
        self.budget = budget
        self.ledger = ledger
        self.call_count = 0

    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        # 预算必须在调用前检查；超限时不允许进入 Provider 调用。
        self.budget.require_budget(request.estimated_cost_cents)
        self.call_count += 1

        # 响应必须先过 finish_reason 状态机，再允许记账和返回。
        classify_finish_reason(
            self.response.finish_reason,
            has_tool_calls=bool(self.response.tool_calls),
        )

        # 只有协议安全的响应才进入真实扣费和 Ledger。
        self.budget.charge(self.response.usage)
        self.ledger.record(
            self.response.request_id,
            self.response.model_name,
            self.response.usage,
        )
        return self.response


class ProviderFactory:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, model_name: str, provider: LLMProvider) -> None:
        # 注册表让上层按 model_name 路由，不直接依赖具体 Provider 类。
        self._providers[model_name] = provider

    def get(self, model_name: str) -> LLMProvider:
        try:
            return self._providers[model_name]
        except KeyError as error:
            raise ProviderNotFoundError(model_name) from error
