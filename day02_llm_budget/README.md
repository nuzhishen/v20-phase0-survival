# Phase 0 Day 2: LLM Runtime Foundations

本目录承接 Day 1 的 FastAPI/Pydantic 基础，完成 Day 2 上午的原理学习与最小可验证代码。

## 范围

- Token 经济学与 Pre-flight 预算。
- 上下文窗口与 KV Cache。
- Temperature/Top_p 参数路由。
- `finish_reason` 状态机。
- Retry 分类决策。

不包含真实 LLM API、Redis、RAG、LangGraph、ReAct 或完整 Provider。

## 文档入口

- `docs/01_token_economics_and_context.md`
- `docs/02_finish_reason_and_retry.md`
- `docs/03_sampling_parameter_routing.md`
- `docs/04_interview_attack_points.md`
- `docs/05_morning_handwritten_notes.md`
- `docs/06_morning_foundation_design.md`
- `docs/07_acceptance_report.md`

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 运行 Mock 演示

```powershell
.\.venv\Scripts\python.exe run_mock_demo.py
```

## 生成 Day 2 下午/晚间报告

```powershell
.\.venv\Scripts\python.exe run_day02_reports.py
```

输出成本报告，并生成：

- `docs/test_reports/day02_compliance.md`
