from __future__ import annotations

from app.agent.schemas import ResearchEvent
from app.error_handling import classify_failure, redact_sensitive, sanitize_failed_event


def test_timeout_error_is_productized_and_retryable() -> None:
    result = classify_failure(
        error=TimeoutError("upstream timed out after 60 seconds"),
        payload={"stage": "report"},
    )

    assert result.code == "task_timeout"
    assert result.retryable is True
    assert result.stage == "report"
    assert "60 seconds" not in result.message


def test_provider_auth_error_is_hidden_from_product_message() -> None:
    raw_event = ResearchEvent(
        job_id="job-1",
        type="failed",
        message="研究任务失败：401 invalid api key sk-secret-value",
        payload={
            "provider": "openai",
            "error": "401 invalid api key sk-secret-value",
            "stage": "search",
        },
    )

    safe_event, result = sanitize_failed_event(raw_event)

    assert result.code == "service_unavailable"
    assert result.retryable is False
    assert "sk-secret-value" not in safe_event.message
    assert "sk-secret-value" not in str(safe_event.payload)
    assert safe_event.payload == {
        "error_code": "service_unavailable",
        "retryable": False,
        "stage": "search",
    }


def test_source_failure_maps_to_source_unavailable() -> None:
    result = classify_failure(
        message="Jina Reader visit failed for all sources",
        payload={"stage": "visit"},
    )

    assert result.code == "source_unavailable"
    assert result.retryable is True


def test_log_redaction_masks_common_api_key_forms() -> None:
    redacted = redact_sensitive(
        "OpenAI sk-secretvalue123 Anthropic api_key=secretvalue456 "
        "Google AIzaSecretValue789 Authorization: BearerToken123"
    )

    assert "secretvalue" not in redacted.lower()
    assert "AIzaSecretValue789" not in redacted
    assert "[REDACTED]" in redacted
