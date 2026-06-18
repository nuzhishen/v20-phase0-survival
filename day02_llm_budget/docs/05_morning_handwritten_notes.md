# 08:00-11:00 手写笔记提纲

## 08:00-09:00 Token 经济学

必须脱稿回答：

1. 一次请求中哪些 token 会计费？
2. 为什么 History 和 Tools Schema 是隐藏成本？
3. 为什么输入价和输出价要分开计算？
4. 为什么预算必须在调用前检查？
5. 估算 usage 与真实 usage 如何结算？

手画：

```text
System 500 + History 800 + User 200 + Tools 600 + Completion 300 = 2400
             ^隐藏开销             ^隐藏开销
```

## 09:00-10:00 上下文与采样参数

必须脱稿回答：

1. 上下文窗口包含什么？
2. KV Cache 为什么随序列长度和并发增长？
3. Lost in the Middle 如何影响证据注入？
4. Temperature 与 Top_p 分别改变什么？
5. 为什么 temperature=0 也不等于绝对确定？

## 10:00-11:00 finish_reason 与 Retry

必须手写状态机：

```text
stop -> parse content
tool_calls -> validate tool name/args/permission/idempotency
length -> TruncationError -> compress/fallback/HITL
content_filter -> safety branch
null/unknown -> ProtocolError
```

必须手写 Retry 死清单：

```text
429 -> retry 3, exponential + jitter
500/502/503 -> retry 2, linear + jitter
timeout -> retry 1 with idempotency
400/401/403 -> no retry
length -> no identical retry
content_filter -> no retry
```

## 自测标准

- 能解释为什么 `tool_calls` 不是异常。
- 能解释为什么 `length` 的“新请求恢复”不等于 Retry。
- 能解释预算只剩 1% 时紧急 OTA 的业务兜底。
- 能在 30 秒内讲清 Pre-flight、finish_reason、Retry 三层防线。

