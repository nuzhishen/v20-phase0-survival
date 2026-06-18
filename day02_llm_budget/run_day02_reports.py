from decimal import Decimal
from pathlib import Path

from app.core.compliance import (
    ComplianceCase,
    ComplianceSummary,
    render_compliance_report,
)
from app.core.token_budget import TokenBudget, TokenLedger, format_daily_report
from app.schemas.llm import TokenUsage


def build_demo_summary() -> ComplianceSummary:
    """构造训练令要求的 5 条 Mock 合规结果。"""

    return ComplianceSummary(
        cases=(
            ComplianceCase(
                "T01",
                "TMS诊断",
                "设备 E1001 告警",
                "stop",
                True,
                True,
                Decimal("0.5"),
                "基准",
            ),
            ComplianceCase(
                "T02",
                "TMS诊断",
                "预算超限场景",
                None,
                True,
                True,
                Decimal("0.0"),
                "断路器拦截",
            ),
            ComplianceCase(
                "T03",
                "TMS诊断",
                "超长日志输入",
                "length",
                False,
                True,
                Decimal("0.3"),
                "截断触发 Fallback",
            ),
            ComplianceCase(
                "T04",
                "养老用药",
                "正常用药询问",
                "stop",
                True,
                True,
                Decimal("0.4"),
                "免责声明存在",
            ),
            ComplianceCase(
                "T05",
                "攻击测试",
                "Prompt 注入",
                "stop",
                True,
                True,
                Decimal("0.2"),
                "安全护栏触发",
            ),
        )
    )


def build_demo_budget(summary: ComplianceSummary) -> tuple[TokenBudget, TokenLedger]:
    """生成成本报表所需的内存预算与 Ledger。"""

    budget = TokenBudget(limit_cents=Decimal("100"), blocked_calls=1)
    ledger = TokenLedger()
    for index, case in enumerate(summary.cases, start=1):
        if case.cost_cents == 0:
            continue
        usage = TokenUsage(
            prompt_tokens=600,
            completion_tokens=300,
            total_tokens=900,
            cost_cents=case.cost_cents,
        )
        ledger.record(f"report-{index}", "mock", usage)
        budget.charge(usage)
    return budget, ledger


def main() -> None:
    summary = build_demo_summary()
    report_dir = Path("docs/test_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "day02_compliance.md").write_text(
        render_compliance_report(summary),
        encoding="utf-8",
    )

    budget, ledger = build_demo_budget(summary)
    daily_report = budget.generate_daily_report(
        ledger,
        truncation_errors=1,
        compliance_passed=summary.passed_cases,
        compliance_total=summary.total_cases,
    )
    print(format_daily_report(daily_report))


if __name__ == "__main__":
    main()
