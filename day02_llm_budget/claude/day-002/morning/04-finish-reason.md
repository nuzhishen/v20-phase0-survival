# 04 finish_reason 生命线：4种状态 + Retry分类决策树

> 目标：finish_reason 是 Agent Runtime 最重要的健康信号。
> 忽视它 = 允许截断JSON进入工具调用链 = 生产事故。

---

## 1. finish_reason 的 4 种状态

### 状态总览

| finish_reason | 含义 | 对 Agent 的影响 | 处理策略 |
|--------------|------|----------------|---------|
| `stop` | 模型自然完成生成 | ✅ 正常，可信任输出 | 正常解析，继续流程 |
| `length` | 达到 max_tokens 上限被截断 | ❌ 输出残缺，JSON可能不完整 | 抛 TruncationError，Fallback |
| `content_filter` | 安全过滤器触发 | ⚠️  输出被审查删除 | 记录告警，返回安全提示 |
| `tool_calls` | 模型请求调用工具 | ✅ 正常，需解析工具调用参数 | 提取 tool_calls，执行工具 |

### 详细分析

#### `stop` — 唯一可信任的正常状态

```
模型主动选择了 <EOS>（end of sequence）token
→ 输出是完整的
→ JSON 结构是闭合的
→ 工具调用参数是完整的
→ 可以安全解析和执行
```

#### `length` — 生产级事故的根源

```
发生条件：生成的 Token 数 ≥ max_tokens 参数设定值
模型被强制截断，它"不知道"自己被截断了

最危险的场景：
┌─────────────────────────────────────────────────────┐
│ 模型正在生成 OTA 指令 JSON：                         │
│                                                     │
│ {                                                   │
│   "action": "create_ota_task",                     │
│   "device_ids": ["SN001", "SN002", "SN0            │
│                                        ↑           │
│                             在这里被截断！           │
│                                                     │
│ Agent 拿到这个 JSON 尝试解析 → JSONDecodeError       │
│ 错误处理不当 → 用空设备列表下发OTA → 静默失败        │
│ 更危险：部分JSON恰好合法 → 用错误参数下发OTA         │
└─────────────────────────────────────────────────────┘
```

#### `content_filter` — 安全审查触发

```
发生条件：输出内容触发模型提供商的安全过滤器
常见场景：
- 养老用药咨询中询问了敏感药物剂量
- TMS 脚本中包含了疑似恶意命令的模式

处理要点：
- 不是错误，是安全机制正常工作
- 记录到 Audit Log（安全事件日志）
- 向用户返回合规的拒绝提示
- 不重试（触发 content_filter 再试会再次触发）
```

#### `tool_calls` — 工具调用请求

```
模型决定需要调用工具（函数调用）来完成任务
此时：
- response.content 可能为空
- response.tool_calls 包含工具名称和参数
- 这是 ReAct 循环中的"Act"步骤

处理流程：
tool_calls → 提取参数 → 验证参数 → 执行工具 → 将结果返回给模型 → 继续循环
```

---

## 2. 为什么 finish_reason=length 不可重试

### 直觉解释

```
问题：上下文太长或 max_tokens 太小导致截断
重试后：相同的上下文 + 相同的 max_tokens → 必然再次截断
重试 = 做无用功 + 再花一次钱
```

### 正确处理流程

```
response.finish_reason == "length"
    ↓
抛出 TruncationError（标记为 NonRetryable）
    ↓
Fallback 策略选择：
    ├── 策略A：压缩上下文后重试（减少 History，重新组织 Prompt）
    ├── 策略B：增大 max_tokens 后重试（需先检查预算）
    └── 策略C：Fallback 到规则引擎（最安全，不依赖LLM）

TMS Agent 选择策略C：
    Fallback 到预定义规则引擎
    基于错误码查历史处置规则
    生成确定性的处理建议
    标记任务为"需人工复核"
```

---

## 3. Retry 分类决策表

### 完整决策表（必须手写记忆）

| 错误码 / 场景 | 是否重试 | 重试策略 | 最大次数 | 理由 |
|-------------|---------|---------|---------|------|
| `429 Rate Limit` | ✅ 是 | 指数退避 | 3次 | 服务端限流是临时的，退避后可恢复 |
| `500 Internal Server Error` | ✅ 是 | 线性退避（2s, 4s） | 2次 | 服务端偶发故障，通常会快速恢复 |
| `502 Bad Gateway` | ✅ 是 | 线性退避（2s, 4s） | 2次 | 网关临时问题 |
| `503 Service Unavailable` | ✅ 是 | 指数退避（+ Jitter） | 3次 | 服务降级，但可能很快恢复 |
| `400 Bad Request` | ❌ 否 | — | 0 | 参数错误，重试必然再次失败 |
| `401 Unauthorized` | ❌ 否 | — | 0 | API Key 无效，重试无意义，应告警 |
| `403 Forbidden` | ❌ 否 | — | 0 | 权限问题，重试无意义 |
| `finish_reason=length` | ❌ 否 | 触发 Fallback | 0 | 上下文溢出，相同参数必然再次截断 |
| `finish_reason=content_filter` | ❌ 否 | 记录审计日志 | 0 | 安全拦截，重试会再次被拦截 |
| 超时（>30s） | ✅ 是 | 立即重试 1 次 | 1次 | 网络抖动，立即重试通常成功 |
| `JSONDecodeError`（解析失败） | ⚠️ 有条件 | 确认 finish_reason 后决定 | — | finish_reason=stop 才可重试；length 则不可重试 |

### 决策树（代码视角）

```python
def should_retry(error: Exception, response: Optional[LLMResponse] = None) -> tuple[bool, str]:
    """
    返回 (是否重试, 重试策略类型)
    策略类型: "exponential" | "linear" | "immediate" | "no_retry"
    """
    
    # finish_reason 优先判断（比错误码更准确）
    if response and response.finish_reason == "length":
        return False, "no_retry"   # 截断，绝对不重试
    
    if response and response.finish_reason == "content_filter":
        return False, "no_retry"   # 安全拦截，不重试
    
    # HTTP 错误码分类
    if isinstance(error, RateLimitError):      # 429
        return True, "exponential"             # 指数退避
    
    if isinstance(error, ServerError):          # 500/502/503
        if error.status_code == 503:
            return True, "exponential"         # 503 可能持续较长，指数退避
        return True, "linear"                  # 500/502 线性退避
    
    if isinstance(error, (BadRequestError,     # 400
                          AuthenticationError,  # 401
                          PermissionError)):    # 403
        return False, "no_retry"               # 客户端错误，不重试
    
    if isinstance(error, TimeoutError):
        return True, "immediate"               # 网络抖动，立即重试一次
    
    # 兜底：未知错误，保守处理，不重试
    return False, "no_retry"
```

### 指数退避实现

```python
import asyncio
import random

async def call_with_retry(provider, request, max_retries=3):
    """指数退避重试，含随机抖动（避免惊群效应）"""
    
    for attempt in range(max_retries + 1):
        try:
            response = await provider.chat_completion(request)
            
            # finish_reason 校验在这里完成
            if response.finish_reason == "length":
                raise TruncationError(
                    f"Response truncated at {response.usage.completion_tokens} tokens"
                )
            
            return response
            
        except (RateLimitError, ServerError) as e:
            retryable, strategy = should_retry(e, None)
            
            if not retryable or attempt == max_retries:
                raise  # 已达最大重试次数，向上抛出
            
            if strategy == "exponential":
                # 指数退避 + 随机抖动
                base_delay = 2 ** attempt          # 1s, 2s, 4s
                jitter = random.uniform(0, base_delay * 0.1)
                delay = base_delay + jitter
            elif strategy == "linear":
                delay = 2.0 * (attempt + 1)        # 2s, 4s
            else:  # immediate
                delay = 0.1
            
            await asyncio.sleep(delay)
```

---

## 4. finish_reason 校验的架构位置

### 必须在哪里校验？

```
┌─────────────────────────────────────────────────────────┐
│ 调用链：Agent → LLMProvider → HTTP Client → LLM API     │
│                                                         │
│        ❌ 错误位置：在 Agent 的工具调用解析层校验        │
│           已经太晚了，解析层拿到的可能已是残缺 JSON      │
│                                                         │
│        ✅ 正确位置：在 LLMProvider.chat_completion()    │
│           HTTP 响应解析完成后立即校验                    │
│           确保向上层暴露的 LLMResponse 永远有完整内容   │
└─────────────────────────────────────────────────────────┘

代码实现：
class LLMProvider(ABC):
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        raw = await self._call_api(request)
        
        # 在这里校验，不是在调用方
        if raw["finish_reason"] not in {"stop", "tool_calls"}:
            if raw["finish_reason"] == "length":
                raise TruncationError(...)
            elif raw["finish_reason"] == "content_filter":
                raise ContentFilterError(...)
        
        return LLMResponse(
            content=raw["content"],
            finish_reason=raw["finish_reason"],
            usage=TokenUsage(...)
        )
```

---

## 5. 面试必背结论

1. **finish_reason 是 Agent 最关键的健康信号**，忽视它是生产事故的根源
2. **length 截断三不做**：不信任输出、不重试、不进入工具调用链
3. **校验位置要在 Provider 层**，不要让残缺响应流出 LLMProvider 边界
4. **429/5xx 可重试，4xx/length/content_filter 不可重试**——这是刚性边界
5. **指数退避必须加 Jitter**，防止多个 Agent 同时重试打垮服务（惊群效应）
