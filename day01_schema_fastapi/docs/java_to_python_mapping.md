# Java 到 Python 工程思维映射

## 1. ThreadPoolExecutor vs asyncio

Java `ThreadPoolExecutor` 通过多个工作线程并发处理任务，阻塞 I/O 会占用线程；Python `asyncio` 使用事件循环和协程，协程在 `await` I/O 时让出执行权。TMS Agent 的 LLM、Redis、Qdrant 和设备服务调用以 I/O 等待为主，因此 Python 异步适合执行面。Java 线程池仍适合认证、审计和任务治理等企业管理面。

## 2. DTO/VO/Validator vs Pydantic BaseModel

Java DTO/VO 配合 Bean Validation 保护 Service 层。Pydantic `BaseModel` 还要保护 Agent 状态机、工具参数和 Checkpoint。设备 ID、失败率或租户信息非法时必须在入口拒绝，否则错误会沿 ReAct、Tool Calling 和重试链路放大。

## 3. Spring Boot Controller vs FastAPI Router

Spring Boot Controller 适合稳定的企业管理 API。FastAPI Router 原生支持异步、Pydantic 和 OpenAPI，更适合承接 Agent Runtime、模型调用和流式响应。Router 是执行链路入口，不只是 Python 版 Controller。

## 4. Java 异常处理 vs FastAPI HTTPException

Java 常用 `@ControllerAdvice` 统一异常响应。FastAPI 可使用 `HTTPException` 和全局异常处理器。Agent Runtime 还必须按失败性质分流：非法输入直接拒绝；网络超时进入重试；持续失败触发熔断、降级或 DLQ。

## 5. Bean Validation vs Pydantic Field

Bean Validation 和 Pydantic `Field` 都能声明必填、长度和值域。Agent 场景中这些约束是安全边界，例如失败率只能是 0 到 1，最大检索数只能是 1 到 20，租户 ID 不允许为空。

## 6. 为什么 Agent Runtime 更适合 Python

Python 的 LLM、RAG、Agent、Eval 和数据处理生态更成熟；`asyncio` 适合编排大量外部 I/O。Python Runtime 负责模型调用、工具执行、状态流转和 SSE，可以降低接入成本并提高迭代速度。

## 7. 为什么 Control Plane 更适合 Java

Java 在 Spring Security、审计、事务、服务治理和存量系统集成方面成熟。Control Plane 负责认证、权限、任务状态、Token 预算、Prompt 版本和 DLQ 重放，追求稳定、可审计和可治理。

## 技术判断

在生产级 Agent 系统中，输入数据不能直接进入 ReAct 或 Tool Calling。我的设计是在 Runtime 入口用 Pydantic 做强约束校验。代价是前期 Schema 设计更重，收益是减少非法状态、工具误调用和后续恢复成本。
