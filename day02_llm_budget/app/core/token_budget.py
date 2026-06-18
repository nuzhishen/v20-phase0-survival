from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

from app.core.exceptions import BudgetExceededError
from app.schemas.llm import TokenUsage


@dataclass(frozen=True)
class LedgerEntry:
    request_id: str
    model_name: str
    usage: TokenUsage
    timestamp: datetime


@dataclass
class TokenLedger:
    entries: list[LedgerEntry] = field(default_factory=list)

    def record(self, request_id: str, model_name: str, usage: TokenUsage) -> None:
        # Ledger 是审计明细：每次调用的模型、usage 和时间都要可追踪。
        self.entries.append(
            LedgerEntry(
                request_id=request_id,
                model_name=model_name,
                usage=usage,
                timestamp=datetime.now(timezone.utc),
            )
        )

    @property
    def total_cost_cents(self) -> Decimal:
        return sum(
            (entry.usage.cost_cents for entry in self.entries),
            start=Decimal("0"),
        )

    @property
    def total_prompt_tokens(self) -> int:
        return sum(entry.usage.prompt_tokens for entry in self.entries)

    @property
    def total_completion_tokens(self) -> int:
        return sum(entry.usage.completion_tokens for entry in self.entries)


@dataclass
class TokenBudget:
    limit_cents: Decimal
    spent_cents: Decimal = Decimal("0")
    blocked_calls: int = 0

    def pre_check(self, estimated_cost_cents: Decimal) -> bool:
        # 等于预算上限也拦截，保留最小运行余量，避免最后一次调用打满预算。
        allowed = self.spent_cents + estimated_cost_cents < self.limit_cents
        if not allowed:
            self.blocked_calls += 1
        return allowed

    def require_budget(self, estimated_cost_cents: Decimal) -> None:
        # 给 Provider 调用层使用：预算不足时直接抛异常，中止后续调用。
        if not self.pre_check(estimated_cost_cents):
            raise BudgetExceededError("Estimated call cost reaches or exceeds budget")

    def charge(self, usage: TokenUsage) -> None:
        # 响应通过协议校验后，按真实 usage 扣费。
        self.spent_cents += usage.cost_cents

    def circuit_break(self) -> bool:
        # 预算达到或超过上限后，外层可以据此触发断路器。
        return self.spent_cents >= self.limit_cents

    def generate_daily_report(
        self,
        ledger: TokenLedger,
        *,
        truncation_errors: int = 0,
        compliance_passed: int = 0,
        compliance_total: int = 0,
    ) -> dict[str, object]:
        """输出今日成本治理报表。

        Day 2 使用内存 Ledger；生产环境应把明细落到数据库或日志系统。
        """

        remaining = max(self.limit_cents - self.spent_cents, Decimal("0"))
        compliance_rate = (
            compliance_passed / compliance_total if compliance_total else 0.0
        )
        return {
            "total_calls": len(ledger.entries),
            "total_prompt_tokens": ledger.total_prompt_tokens,
            "total_completion_tokens": ledger.total_completion_tokens,
            "total_cost_cents": self.spent_cents,
            "budget_remaining_cents": remaining,
            "circuit_breaker_triggered": self.blocked_calls,
            "truncation_errors": truncation_errors,
            "compliance_rate": compliance_rate,
            "compliance_passed": compliance_passed,
            "compliance_total": compliance_total,
        }


def format_daily_report(report: dict[str, object]) -> str:
    """把成本治理报表格式化为训练令要求的控制台输出。"""

    compliance_rate = int(cast(float, report["compliance_rate"]) * 100)
    return "\n".join(
        [
            "=== Day 02 Token Cost Report ===",
            f"Total Calls: {report['total_calls']}",
            f"Total Prompt Tokens: {report['total_prompt_tokens']}",
            f"Total Completion Tokens: {report['total_completion_tokens']}",
            f"Total Cost: {report['total_cost_cents']} cents",
            f"Budget Remaining: {report['budget_remaining_cents']} cents",
            f"Circuit Breaker Triggered: {report['circuit_breaker_triggered']}",
            f"Truncation Errors: {report['truncation_errors']}",
            "Compliance Rate: "
            f"{compliance_rate}% "
            f"({report['compliance_passed']}/{report['compliance_total']})",
        ]
    )
