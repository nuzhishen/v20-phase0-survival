from dataclasses import dataclass
from enum import StrEnum
from random import uniform
from typing import Callable

from app.core.exceptions import (
    ContentFilteredError,
    ProtocolError,
    TruncationError,
)


class FailureKind(StrEnum):
    HTTP = "http"
    TIMEOUT = "timeout"
    RUNTIME = "runtime"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    status_code: int | None = None
    error: Exception | None = None


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    delays_seconds: tuple[float, ...]
    reason: str
    fallback_required: bool = False


JitterSource = Callable[[float, float], float]


def _with_jitter(
    base_delays: tuple[float, ...],
    jitter_source: JitterSource,
    jitter_ratio: float = 0.2,
) -> tuple[float, ...]:
    # 为每次退避增加 0%~20% 随机抖动，避免大量请求同时重试形成流量尖峰。
    return tuple(
        base_delay + jitter_source(0.0, base_delay * jitter_ratio)
        for base_delay in base_delays
    )


def decide_retry(
    failure: Failure,
    *,
    jitter_source: JitterSource = uniform,
) -> RetryDecision:
    # Runtime 协议错误不做“原样重试”，必须进入压缩上下文、降级或人工处理。
    if isinstance(
        failure.error,
        (TruncationError, ContentFilteredError, ProtocolError),
    ):
        return RetryDecision(
            False,
            (),
            "Runtime response errors require recovery, not identical retry",
            fallback_required=True,
        )

    if failure.kind == FailureKind.TIMEOUT:
        # 超时可能是网络抖动，只允许一次有限重试，真实执行层还要配合幂等键。
        return RetryDecision(
            True,
            _with_jitter((0.5,), jitter_source),
            "One bounded retry with jitter for network instability",
        )

    if failure.status_code == 429:
        # 限流通常是临时状态，用指数退避逐步降低请求压力。
        return RetryDecision(
            True,
            _with_jitter((1.0, 2.0, 4.0), jitter_source),
            "Rate limit: exponential backoff with 20% jitter",
        )

    if failure.status_code in {500, 502, 503}:
        # 5xx 可能是服务端瞬时故障，次数必须有限，避免故障放大。
        return RetryDecision(
            True,
            _with_jitter((1.0, 2.0), jitter_source),
            "Transient server failure: bounded linear backoff with 20% jitter",
        )

    if failure.status_code in {400, 401, 403}:
        # 参数或鉴权问题不会因重复请求变好，必须修请求或修凭证。
        return RetryDecision(False, (), "Request or authentication must be fixed")

    return RetryDecision(False, (), "Unknown failures are not retried by default")
