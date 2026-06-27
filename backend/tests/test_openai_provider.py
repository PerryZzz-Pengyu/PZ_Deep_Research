from __future__ import annotations

import pytest

from app.agent.providers.openai_provider import _supports_temperature


@pytest.mark.parametrize("model", [
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5-nano",
    "gpt-5-mini",
    "claude-sonnet-4-6",
    "gemini-2.5-flash",
])
def test_supports_temperature_standard_models(model: str) -> None:
    assert _supports_temperature(model) is True


@pytest.mark.parametrize("model", [
    "gpt-5.5",
    "GPT-5.5",   # case-insensitive
    "o1",
    "o1-mini",
    "o1-preview",
    "o3",
    "o3-mini",
    "o4-mini",
])
def test_supports_temperature_rejects_reasoning_models(model: str) -> None:
    assert _supports_temperature(model) is False
