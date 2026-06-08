from __future__ import annotations

from app.config import get_settings, missing_provider_requirements


def test_get_settings_uses_provider_default_models_when_env_is_blank(monkeypatch) -> None:
    for name in [
        "DEFAULT_MODEL",
        "OPENAI_MODEL",
        "OPENAI_MODEL_OPTIONS",
        "ANTHROPIC_MODEL",
        "GEMINI_MODEL",
    ]:
        monkeypatch.setenv(name, "")

    settings = get_settings()

    assert settings.openai_model == "gpt-5.4-mini"
    assert settings.openai_base_url == "https://api.openai.com/v1"
    assert settings.openai_model_options[:4] == (
        "gpt-5.4-mini",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-nano",
    )
    assert settings.anthropic_model == "claude-sonnet-4-6"
    assert settings.gemini_model == "gemini-2.5-flash"


def test_get_settings_expands_localhost_cors_aliases(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    settings = get_settings()

    assert settings.cors_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )


def test_get_settings_reads_mock_provider_delay(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_PROVIDER_DELAY_SECONDS", "1.25")

    settings = get_settings()

    assert settings.mock_provider_delay_seconds == 1.25


def test_get_settings_normalizes_postgresql_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost/research")

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:password@localhost/research"


def test_get_settings_ignores_chinese_placeholders(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "在这里填写你的OpenAI_API_Key")
    monkeypatch.setenv("OPENAI_MODEL", "在这里填写你要使用的OpenAI模型")
    monkeypatch.setenv("SERPAPI_API_KEY", "在这里填写你的SerpAPI_Key")
    monkeypatch.setenv("JINA_API_KEY", "在这里填写你的Jina_API_Key")

    settings = get_settings()

    assert settings.openai_api_key == ""
    assert settings.openai_model == "gpt-5.4-mini"
    assert settings.serpapi_api_key == ""
    assert settings.jina_api_key == ""


def test_missing_provider_requirements_requires_key_and_real_search(monkeypatch) -> None:
    for name in ["OPENAI_API_KEY", "SERPAPI_API_KEY"]:
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("SEARCH_PROVIDER", "serpapi")

    settings = get_settings()

    assert missing_provider_requirements(settings, "openai") == [
        "OPENAI_API_KEY",
        "SERPAPI_API_KEY",
    ]


def test_missing_provider_requirements_accepts_ready_provider(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("SEARCH_PROVIDER", "serpapi")
    monkeypatch.setenv("SERPAPI_API_KEY", "serpapi-key")

    settings = get_settings()

    assert missing_provider_requirements(settings, "anthropic") == []
