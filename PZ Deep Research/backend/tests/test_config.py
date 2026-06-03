from __future__ import annotations

from app.config import get_settings, missing_provider_requirements


def test_get_settings_uses_provider_default_models_when_env_is_blank(monkeypatch) -> None:
    for name in [
        "DEFAULT_MODEL",
        "OPENAI_MODEL",
        "ANTHROPIC_MODEL",
        "GEMINI_MODEL",
    ]:
        monkeypatch.setenv(name, "")

    settings = get_settings()

    assert settings.openai_model == "gpt-5-mini"
    assert settings.anthropic_model == "claude-sonnet-4-6"
    assert settings.gemini_model == "gemini-2.5-flash"


def test_missing_provider_requirements_requires_key_and_real_search(monkeypatch) -> None:
    for name in ["OPENAI_API_KEY", "SERPER_API_KEY"]:
        monkeypatch.setenv(name, "")

    settings = get_settings()

    assert missing_provider_requirements(settings, "openai") == [
        "OPENAI_API_KEY",
        "SERPER_API_KEY",
    ]


def test_missing_provider_requirements_accepts_ready_provider(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")

    settings = get_settings()

    assert missing_provider_requirements(settings, "anthropic") == []
