  ┌──────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┐
  │               文件               │                                     用途                                      │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ README.md                        │ Day 2 总览 + 文件索引 + 今日核心技术判断                                      │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/00-quick-reference.md    │ 先看这个 — 3张手写表 + 08:00-11:00学习路径                                    │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/01-token-economics.md    │ Token经济学：输入/输出定价、Tools Schema隐藏成本、Pre-flight预检原理          │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/02-context-window.md     │ KV Cache显存原理、Lost in the Middle研究结论、长对话膨胀公式 + 生产级压缩策略 │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/03-temperature-params.md │ Temperature/Top_p数学原理 + 完整8场景路由矩阵（含代码实现）                   │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/04-finish-reason.md      │ 4种状态详解、length灾难场景图解、Retry决策树代码、校验的正确架构位置          │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ morning/05-interview-attacks.md  │ 3道高频追问的4层递进答案 + 30秒综合话术 + 备用QA                              │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ diagrams/token-distribution.mmd  │ Mermaid饼图：Token消耗分布                                                    │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ diagrams/retry-decision-tree.mmd │ Mermaid流程图：Retry完整决策树（含熔断器 + 模型切换）                         │
  ├──────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ diagrams/llm-call-flow.mmd       │ Mermaid时序图：完整调用链路（Budget→Provider→finish_reason→Ledger）           │
  └──────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────┘

# Phase 0 Day 2 — Token经济学 + LLM调用层 + 预算断路器

**日期**：2026-06-09（周二）  
**主题**：Token经济学 / finish_reason生命线 / Retry分类 / Temperature路由  
**目标**：可运行的LLMProvider抽象层 + 预算断路器 + 3个手写System Prompt

---

## 文件索引

| 文件 | 内容 |
|------|------|
| [morning/01-token-economics.md](morning/01-token-economics.md) | Token经济学：定价模型、隐藏开销、成本分布图 |
| [morning/02-context-window.md](morning/02-context-window.md) | 上下文窗口：KV Cache、Lost in the Middle、长对话膨胀 |
| [morning/03-temperature-params.md](morning/03-temperature-params.md) | Temperature/Top_p：参数原理 + 场景路由矩阵 |
| [morning/04-finish-reason.md](morning/04-finish-reason.md) | finish_reason生命线：4种状态 + Retry分类决策树 |
| [morning/05-interview-attacks.md](morning/05-interview-attacks.md) | 面试攻击点：3道高频追问 + 标准答案框架 |
| [morning/diagrams/token-distribution.mmd](morning/diagrams/token-distribution.mmd) | Mermaid：Token消耗分布图 |
| [morning/diagrams/retry-decision-tree.mmd](morning/diagrams/retry-decision-tree.mmd) | Mermaid：Retry分类决策树 |
| [morning/diagrams/llm-call-flow.mmd](morning/diagrams/llm-call-flow.mmd) | Mermaid：LLM调用时序图 |

---

## 今日核心技术判断（必须脱稿）

> 在生产级 Agent 系统中，LLM响应的 `finish_reason` 不能简单信任默认的 `stop`，
> 因为 `length` 截断会导致 Agent 拿到残缺 JSON 并触发不可预期的工具调用。
> 我的设计选择是：在 LLMResponse 解析层**强制校验** `finish_reason`，
> 非 `stop` 立即抛 `TruncationError` 并触发 Fallback 到规则引擎，
> 同时将该请求标记为**不可重试**。
> 代价：损失了部分长文本任务的自动处理能力。
> 收益：彻底杜绝了因截断导致的 Agent 运行时崩溃和安全事故。

---

## 今日验收清单

- [ ] 手写 Retry 分类决策表（纸质）
- [ ] 手写 Token 消耗分布图（纸质）
- [ ] 手写 Temperature 决策矩阵（纸质）
- [ ] 能脱稿回答 3 道面试追问
- [ ] 能用 30 秒说清"为什么 finish_reason=length 不可重试"
