from enum import StrEnum

from app.core.exceptions import (
    ContentFilteredError,
    ProtocolError,
    TruncationError,
)


class FinishReason(StrEnum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"


class ResponseAction(StrEnum):
    PARSE_CONTENT = "parse_content"
    VALIDATE_TOOL_CALLS = "validate_tool_calls"


def classify_finish_reason(
    finish_reason: str | None,
    *,
    has_tool_calls: bool = False,
) -> ResponseAction:
    # stop 表示普通自然语言/JSON 输出结束，可以进入内容解析。
    if finish_reason == FinishReason.STOP:
        return ResponseAction.PARSE_CONTENT

    # tool_calls 是 Agent 的正常状态，不是异常；但必须存在真实工具调用数据。
    if finish_reason == FinishReason.TOOL_CALLS:
        if not has_tool_calls:
            raise ProtocolError("finish_reason=tool_calls without tool call data")
        return ResponseAction.VALIDATE_TOOL_CALLS

    # length 是高危状态：输出可能是残缺 JSON 或残缺工具参数，禁止继续解析。
    if finish_reason == FinishReason.LENGTH:
        raise TruncationError(
            "LLM output was truncated; do not parse or retry the same request"
        )

    # content_filter 不是可用性故障，应该进入安全分支，而不是重试。
    if finish_reason == FinishReason.CONTENT_FILTER:
        raise ContentFilteredError("LLM response was blocked by a safety filter")

    # null/未知值说明 Provider 协议异常，必须显式失败。
    raise ProtocolError(f"Unsupported finish_reason: {finish_reason!r}")
