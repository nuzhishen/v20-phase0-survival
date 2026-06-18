# AI 协作与测试记录

## AI 协助范围

- 生成 FastAPI 最小工程骨架。
- 实现三个业务 Schema 的字段和约束。
- 生成正常、异常、边界和 HTTP 校验测试。
- 整理 README、Mermaid 请求流转图和项目规则。

## 人必须掌握的内容

- 为什么选择字段和值域。
- 为什么入口校验失败不能进入 Agent 链路。
- Python `asyncio` 与 Java 线程池的差异。
- 后续 Checkpoint、Retry、熔断和权限矩阵的设计权衡。

## 测试报告

执行命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
25 passed, 1 warning in 0.41s
```

告警来自 FastAPI/Starlette `TestClient` 对当前 `httpx` 的弃用提示，不影响本次功能与验收。后续升级依赖时处理，不在 Day 1 扩大范围。

测试过程中发现：全局严格模式会拒绝 HTTP JSON 中合法的 ISO 8601 时间字符串。最终保留全局严格校验，只对两个 `datetime` 字段允许受控解析，避免放宽布尔、整数和浮点字段。

## 服务验证

- Uvicorn 在 `127.0.0.1:8000` 启动成功。
- `GET /health` 返回 `status=ok`。
- `GET /docs` 返回 HTTP 200。
- Swagger UI 标识检查通过。
- 验证结束后已关闭临时 Uvicorn 进程。

## 后续故障测试

- 必填字段缺失。
- JSON 类型错误。
- 外部服务超时。
- 上游脏数据和未知字段。
