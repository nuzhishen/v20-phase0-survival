# Phase 0 Day 1 面试攻击点答案

## 1. 你为什么用 Python 做 Agent Runtime，而不是全 Java？

我不是否定 Java，而是做职责分离。Agent Runtime 的核心工作是 LLM 调用、RAG 检索、Tool Calling、SSE 流式输出、Eval 和状态编排，这些生态在 Python 侧更成熟，接入成本更低。  

Java 更适合 Control Plane，负责认证、审计、任务治理、Token 预算、Prompt 版本和 DLQ 重放。  

所以我的架构是 Java 管治理，Python 管执行。这样既能利用 Python AI 生态，又能保留 Java 企业系统的稳定性。

## 2. Pydantic 在 Agent 系统里解决什么生产问题？

Pydantic 解决的是 Agent Runtime 的输入边界问题。  

在传统系统里，DTO 校验失败通常只是业务接口失败。但在 Agent 系统里，非法输入可能污染 ReAct 状态机、生成错误工具参数、写入错误 Checkpoint，甚至触发错误的 OTA 或脚本操作。

例如 `failure_rate_7d` 超过 1、`device_id` 为空、`tenant_id` 缺失，都不能进入 Agent 链路。  

所以 Pydantic 是第一道 Harness：先做类型、必填、范围和值域校验，再允许进入 Agent 编排。

## 3. Python 异步和 Java 线程池的本质差异是什么？

Java 线程池是多线程模型，任务由多个工作线程执行，阻塞 I/O 会占住线程。它适合传统企业后端和阻塞式生态。

Python `asyncio` 是事件循环加协程模型。协程遇到 `await` 时主动让出控制权，事件循环继续调度其他任务。它不是多线程，不适合直接跑 CPU 密集任务，但非常适合 LLM API、Redis、Qdrant、设备服务这类 I/O 密集调用。

一句话：Java 线程池靠线程并发，Python 异步靠 I/O 等待期间的协作式调度。

## 4. 如果 LLM 调用超时，FastAPI 异步接口怎么处理？

我会分三层处理。

第一层是调用级超时，例如用 `asyncio.wait_for` 或 HTTP client timeout 限制 LLM 请求时间。

第二层是业务级重试，按失败类型判断是否重试。网络超时可以重试，参数错误不能重试。

第三层是降级和状态记录。如果重试耗尽，就写入任务状态、Checkpoint 或 DLQ，必要时返回降级结果，而不是让请求无限挂起。

关键点是：超时不能只靠接口层硬等，要进入 Harness 机制，结合 Retry、Circuit Breaker、Fallback 和 DLQ。

## 5. Schema 校验失败是否应该进入 Agent 执行链路？为什么？

不应该。

Schema 校验失败说明请求还没有满足 Runtime 的最低数据契约。如果让它进入 Agent 链路，后续 ReAct、Tool Calling、Checkpoint、Retry 都可能基于错误状态继续执行，风险会放大。

正确做法是在入口直接返回 422，并记录必要日志。只有通过 Pydantic 校验的数据，才允许进入 Agent 状态机。

我的原则是：入口非法数据直接拒绝，外部服务失败才进入 Harness 治理。

