from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

from app.agent.schemas import ResearchEvent


ProductErrorCode = Literal[
    "network_error",
    "service_unavailable",
    "task_timeout",
    "source_unavailable",
    "insufficient_credits",
    "content_unsupported",
    "system_error",
]


@dataclass(frozen=True)
class ProductError:
    code: ProductErrorCode
    message: str
    retryable: bool
    stage: str | None = None


_PRODUCT_MESSAGES: dict[ProductErrorCode, str] = {
    "network_error": "网络连接不稳定，请检查网络后重试。",
    "service_unavailable": "研究服务暂时繁忙，请稍后重试。",
    "task_timeout": "本次研究未能在规定时间内完成，请重试。",
    "source_unavailable": "暂时无法获取足够的可用资料，请调整问题或稍后重试。",
    "insufficient_credits": "当前积分不足，无法继续研究。",
    "content_unsupported": "当前问题暂时无法处理，请调整后重试。",
    "system_error": "研究过程中出现异常，请稍后重试。",
}


def product_error(
    code: ProductErrorCode,
    *,
    retryable: bool,
    stage: str | None = None,
) -> ProductError:
    return ProductError(
        code=code,
        message=_PRODUCT_MESSAGES[code],
        retryable=retryable,
        stage=stage,
    )


def classify_failure(
    *,
    error: BaseException | None = None,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> ProductError:
    payload = payload or {}
    stage_value = payload.get("stage")
    stage = stage_value if isinstance(stage_value, str) and stage_value else None
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    raw = " ".join(
        part
        for part in (
            message,
            str(error or ""),
            str(payload.get("error", "")),
            str(payload.get("reason", "")),
        )
        if part
    ).lower()

    if isinstance(error, TimeoutError) or any(
        marker in raw for marker in ("timeout", "timed out", "超时")
    ):
        return product_error("task_timeout", retryable=True, stage=stage)

    if any(
        marker in raw
        for marker in (
            "insufficient_credits",
            "insufficient credits",
            "credit balance",
            "积分不足",
        )
    ):
        return product_error("insufficient_credits", retryable=False, stage=stage)

    if any(
        marker in raw
        for marker in (
            "content policy",
            "safety policy",
            "blocked by safety",
            "unsupported content",
            "内容不支持",
        )
    ):
        return product_error("content_unsupported", retryable=False, stage=stage)

    if stage in {"search", "visit", "evidence"} and any(
        marker in raw
        for marker in (
            "source",
            "search",
            "visit",
            "reader",
            "jina",
            "serpapi",
            "资料",
            "来源",
            "访问",
        )
    ):
        return product_error("source_unavailable", retryable=True, stage=stage)

    if any(
        marker in raw
        for marker in (
            "connection",
            "network",
            "dns",
            "socket",
            "fetch",
            "broken pipe",
            "connection reset",
            "网络",
            "连接失败",
        )
    ):
        return product_error("network_error", retryable=True, stage=stage)

    try:
        status_code = int(status)
    except (TypeError, ValueError):
        status_code = None

    if status_code in {408, 409, 425, 429, 500, 502, 503, 504, 529} or any(
        marker in raw
        for marker in (
            "rate limit",
            "resource_exhausted",
            "unavailable",
            "overloaded",
            "high demand",
            "temporar",
            "service_restarted",
            "服务重启",
            "模型没有返回结果",
        )
    ):
        return product_error("service_unavailable", retryable=True, stage=stage)

    if status_code in {400, 401, 403, 404, 422} or any(
        marker in raw
        for marker in (
            "invalid api key",
            "authentication",
            "permission",
            "configuration",
            "配置",
        )
    ):
        return product_error("service_unavailable", retryable=False, stage=stage)

    if stage == "report":
        return product_error("system_error", retryable=True, stage=stage)
    return product_error("system_error", retryable=True, stage=stage)


def sanitize_failed_event(event: ResearchEvent) -> tuple[ResearchEvent, ProductError]:
    classified = classify_failure(message=event.message, payload=event.payload)
    safe_event = event.model_copy(
        update={
            "message": classified.message,
            "payload": {
                "error_code": classified.code,
                "retryable": classified.retryable,
                "stage": classified.stage,
            },
        }
    )
    return safe_event, classified


def redact_sensitive(value: Any) -> str:
    text = str(value)
    patterns = (
        r"\bsk-[A-Za-z0-9_-]{8,}\b",
        r"\bAIza[A-Za-z0-9_-]{8,}\b",
        r"\b(?:api[_ -]?key|authorization|bearer)\s*[:=]?\s*[A-Za-z0-9._-]{8,}\b",
    )
    for pattern in patterns:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
    return text
