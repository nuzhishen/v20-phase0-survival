# Codex Project Instructions

## Phase 0 Scope

- This repository is the V20 Phase 0 survival week, not the P1 production project.
- Keep Day 1 through Day 5 independently runnable. Day 6 owns cross-day integration.
- Do not introduce WebSocket. Future streaming work must use SSE.
- Do not introduce LangGraph, MCP, Redis, a frontend, an admin dashboard, or platform-style services during Phase 0.
- Do not implement P2 Context Engine or P3 Control Plane features here.

## Daily Boundaries

- Day 1: FastAPI, Pydantic v2, strict validation, thin routes, tests, and docs only.
- Day 2: provider contracts, Mock provider, token budget, retry classification, prompts, compliance, and reports.
- Day 3: implement the ReAct decision loop manually. Framework-generated core loops are not allowed.
- Day 4: implement only chunk -> embed -> upsert -> search -> top_k.
- Day 5: build on Day 4 and compare dense retrieval with hybrid retrieval plus reranking.
- Day 6: integrate Day 2 through Day 5 against the fixed pass-test scenario.

## Engineering Rules

- Reject unknown input fields and unsafe implicit coercion.
- Add or update tests whenever behavior or validation changes.
- Preserve the Day 1 and Day 2 migrated baselines unless a concrete defect requires a fix.
- Keep imports local to each day. Both migrated projects currently use a top-level `app` package.
- Run each day's tests in a separate process and working directory.
- Add selective Chinese comments only where they explain a decision or boundary.
- Core Harness decisions such as checkpoint granularity, retry trees, circuit-breaker thresholds, fallback triggers, and tool permissions must be designed and explainable by the engineer.

