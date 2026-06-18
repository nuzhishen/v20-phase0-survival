from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import BudgetExceededError


@dataclass(frozen=True)
class TokenBreakdown:
    """一次 LLM 请求的 Token 分布。

    history 和 tools_schema 是用户不直接感知、但会参与计费的隐藏开销。
    """

    system_prompt: int
    history: int
    user_query: int
    tools_schema: int
    completion: int

    @property
    def prompt_tokens(self) -> int:
        # Provider 的输入计费通常包含 system、history、user、tools schema。
        return (
            self.system_prompt
            + self.history
            + self.user_query
            + self.tools_schema
        )

    @property
    def hidden_tokens(self) -> int:
        # 这部分经常被 Agent 开发者忽略，是成本膨胀的主要来源。
        return self.history + self.tools_schema

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion


@dataclass(frozen=True)
class ModelPrice:
    """模型价格配置。

    输入和输出价格通常不同，必须分开建模，不能只按 total_tokens 粗算。
    """

    input_per_million: Decimal
    output_per_million: Decimal


def estimate_cost(breakdown: TokenBreakdown, price: ModelPrice) -> Decimal:
    """按输入/输出分价估算本次请求成本。"""

    million = Decimal(1_000_000)
    input_cost = Decimal(breakdown.prompt_tokens) / million * price.input_per_million
    output_cost = (
        Decimal(breakdown.completion) / million * price.output_per_million
    )
    return input_cost + output_cost


def preflight_budget(
    *,
    estimated_cost: Decimal,
    spent: Decimal,
    limit: Decimal,
    reserve_ratio: Decimal = Decimal("0.01"),
) -> None:
    """调用 LLM 之前做预算预检。

    事后统计无法挽回已经发生的成本，所以必须在请求发出前拦截。
    reserve_ratio 用于保留最小运行余量，避免预算被一次请求打满。
    """

    usable_limit = limit * (Decimal("1") - reserve_ratio)
    if spent + estimated_cost > usable_limit:
        raise BudgetExceededError(
            f"Projected spend {spent + estimated_cost} exceeds usable limit "
            f"{usable_limit}"
        )
