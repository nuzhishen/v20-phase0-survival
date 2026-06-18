class LLMRuntimeError(Exception):
    "Day 2 运行时策略的基础异常。"


class TruncationError(LLMRuntimeError):
    "Provider 返回 length 截断时抛出，禁止解析残缺响应。"


class ContentFilteredError(LLMRuntimeError):
    "Provider 安全过滤拦截内容时抛出。"


class ProtocolError(LLMRuntimeError):
    "Provider 响应不符合预期协议时抛出。"


class BudgetExceededError(LLMRuntimeError):
    "LLM 调用前预算预检失败时抛出。"
