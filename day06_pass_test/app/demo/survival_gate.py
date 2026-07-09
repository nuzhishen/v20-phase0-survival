from __future__ import annotations

import json
import sys

from app.agent.diagnosis_pipeline import calculate_metrics, run_gate_cases


def main() -> None:
    """运行 Day6 通关 Demo，并输出真实指标摘要。"""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    outcomes = run_gate_cases()
    metrics = calculate_metrics(outcomes)
    payload = {
        "metrics": {
            "total_cases": metrics.total_cases,
            "passed_cases": metrics.passed_cases,
            **metrics.to_percent_dict(),
        },
        "cases": [
            {
                "case_id": outcome.case.case_id,
                "name": outcome.case.name,
                "crashed": outcome.crashed,
                "error": outcome.error,
                "status": None if outcome.result is None else outcome.result.status,
                "fallback_path": None if outcome.result is None else outcome.result.fallback_path,
                "fallback_reason": None if outcome.result is None else outcome.result.fallback_reason,
                "require_hitl": None if outcome.result is None else outcome.result.require_hitl,
                "risk_level": None if outcome.result is None else outcome.result.risk_level,
                "rag_refs": []
                if outcome.result is None
                else [ref.chunk_id for ref in outcome.result.rag_references],
                "actions": []
                if outcome.result is None
                else [step.action for step in outcome.result.react_trace],
            }
            for outcome in outcomes
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
