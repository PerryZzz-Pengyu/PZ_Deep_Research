from __future__ import annotations

from app.config import get_settings, missing_provider_requirements, resolve_model_route


def test_get_settings_uses_provider_default_models_when_env_is_blank(monkeypatch) -> None:
    for name in [
        "DEFAULT_MODEL",
        "OPENAI_MODEL",
        "OPENAI_MODEL_OPTIONS",
        "EVIDENCE_EXTRACTION_MODEL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_MODEL_OPTIONS",
        "ANTHROPIC_EVIDENCE_MODEL",
        "GEMINI_MODEL",
        "GEMINI_MODEL_OPTIONS",
        "GEMINI_EVIDENCE_MODEL",
        "LLM_MAX_RETRIES",
        "LLM_RETRY_BASE_DELAY_SECONDS",
        "MODEL_ROUTING_MODE",
        "PRODUCTION_PROVIDER",
        "PRODUCTION_MODEL",
        "MODEL_ROUTING_VERSION",
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
    assert settings.anthropic_model_options[:3] == (
        "claude-sonnet-4-6",
        "claude-opus-4-8",
        "claude-opus-4-7",
    )
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_model_options[:3] == (
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
    )
    assert settings.llm_max_retries == 3
    assert settings.llm_retry_base_delay_seconds == 2.0
    assert settings.evidence_extraction_model == "gpt-5-nano"
    assert settings.anthropic_evidence_model == "claude-haiku-4-5-20251001"
    assert settings.gemini_evidence_model == "gemini-2.5-flash-lite"
    assert settings.model_routing_mode == "production"
    assert settings.production_provider == "openai"
    assert settings.production_model == "gpt-5.4-mini"
    assert settings.model_routing_version == "openai-default-v1"


def test_production_model_route_ignores_client_provider_and_model() -> None:
    settings = get_settings()

    route = resolve_model_route(
        settings,
        requested_provider="anthropic",
        requested_model="claude-opus-4-8",
    )

    assert route.provider == "openai"
    assert route.model == "gpt-5.4-mini"
    assert route.routing_version == "openai-default-v1"
    assert route.selection_enabled is False


def test_manual_model_route_preserves_internal_selection() -> None:
    settings = get_settings()
    manual_settings = settings.__class__(
        **{
            **settings.__dict__,
            "model_routing_mode": "manual",
        }
    )

    route = resolve_model_route(
        manual_settings,
        requested_provider="gemini",
        requested_model="gemini-2.5-flash",
    )

    assert route.provider == "gemini"
    assert route.model == "gemini-2.5-flash"
    assert route.routing_version == "manual"
    assert route.selection_enabled is True


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
    monkeypatch.setenv(
        "DATABASE_MIGRATION_URL",
        "postgres://user:password@direct.example/research",
    )
    monkeypatch.setenv("DATABASE_POOL_SIZE", "7")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "3")

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:password@localhost/research"
    assert (
        settings.database_migration_url
        == "postgresql+psycopg://user:password@direct.example/research"
    )
    assert settings.database_pool_size == 7
    assert settings.database_max_overflow == 3


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
