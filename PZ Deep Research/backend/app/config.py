from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL_OPTIONS = (
    "gpt-5.4-mini",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-nano",
    "gpt-5-mini",
    "gpt-5-nano",
)
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_SEARCH_PROVIDER = "serpapi"
DEFAULT_ACADEMIC_SEARCH_ENGINE = "google_scholar"


@dataclass(frozen=True)
class Settings:
    app_name: str = "PZ Deep Research API"
    default_provider: str = "mock"
    default_model: str = ""
    llm_max_retries: int = 1
    llm_timeout_seconds: float = 60.0
    openai_api_key: str = ""
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    openai_model: str = ""
    openai_model_options: tuple[str, ...] = DEFAULT_OPENAI_MODEL_OPTIONS
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    search_provider: str = DEFAULT_SEARCH_PROVIDER
    academic_search_engine: str = DEFAULT_ACADEMIC_SEARCH_ENGINE
    serpapi_api_key: str = ""
    jina_api_key: str = ""
    visit_max_concurrency: int = 5
    evidence_extraction_model: str = "gpt-5-nano"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value.startswith("在这里填写"):
        return default
    return value or default


def _get_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _get_env(name, "")
    if not raw:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


def get_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return Settings(
        default_provider=_get_env("DEFAULT_PROVIDER", "mock"),
        default_model=_get_env("DEFAULT_MODEL", ""),
        llm_max_retries=_get_int_env("LLM_MAX_RETRIES", 1),
        llm_timeout_seconds=_get_float_env("LLM_TIMEOUT_SECONDS", 60.0),
        openai_api_key=_get_env("OPENAI_API_KEY", ""),
        openai_base_url=_get_env("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        openai_model=_get_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        openai_model_options=_get_csv_env("OPENAI_MODEL_OPTIONS", DEFAULT_OPENAI_MODEL_OPTIONS),
        anthropic_api_key=_get_env("ANTHROPIC_API_KEY", ""),
        anthropic_model=_get_env("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        gemini_api_key=_get_env("GEMINI_API_KEY", ""),
        gemini_model=_get_env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        search_provider=_get_env("SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER).lower(),
        academic_search_engine=_get_env("ACADEMIC_SEARCH_ENGINE", DEFAULT_ACADEMIC_SEARCH_ENGINE),
        serpapi_api_key=_get_env("SERPAPI_API_KEY", ""),
        jina_api_key=_get_env("JINA_API_KEY", ""),
        visit_max_concurrency=_get_int_env("VISIT_MAX_CONCURRENCY", 5),
        evidence_extraction_model=_get_env("EVIDENCE_EXTRACTION_MODEL", "gpt-5-nano"),
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )


def missing_search_requirements(settings: Settings) -> list[str]:
    if settings.search_provider == "serpapi":
        return [] if settings.serpapi_api_key else ["SERPAPI_API_KEY"]
    if settings.search_provider == "mock":
        return []
    return ["SUPPORTED_SEARCH_PROVIDER"]


def provider_model(settings: Settings, provider: str, model_override: str | None = None) -> str:
    if model_override:
        return model_override
    if provider == "openai":
        return settings.openai_model or settings.default_model
    if provider == "anthropic":
        return settings.anthropic_model or settings.default_model
    if provider == "gemini":
        return settings.gemini_model or settings.default_model
    return ""


def missing_provider_requirements(
    settings: Settings,
    provider: str,
    *,
    model_override: str | None = None,
    require_real_search: bool = True,
) -> list[str]:
    normalized = provider.lower()
    missing: list[str] = []
    if normalized == "mock":
        return missing
    if normalized == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    elif normalized == "anthropic" and not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    elif normalized == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    elif normalized not in {"openai", "anthropic", "gemini"}:
        missing.append("SUPPORTED_PROVIDER")

    if normalized in {"openai", "anthropic", "gemini"} and not provider_model(
        settings,
        normalized,
        model_override,
    ):
        missing.append(f"{normalized.upper()}_MODEL")

    if require_real_search and normalized in {"openai", "anthropic", "gemini"}:
        missing.extend(missing_search_requirements(settings))
    return missing
