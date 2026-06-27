from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

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
DEFAULT_ANTHROPIC_MODEL_OPTIONS = (
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_GEMINI_MODEL_OPTIONS = (
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
DEFAULT_OPENAI_EVIDENCE_MODEL = "gpt-5-nano"
DEFAULT_ANTHROPIC_EVIDENCE_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_GEMINI_EVIDENCE_MODEL = "gemini-2.5-flash-lite"
DEFAULT_CLOUD_ROUTING_VERSION = "cloud-unconfigured"
DEFAULT_SEARCH_PROVIDER = "serpapi"
DEFAULT_ACADEMIC_SEARCH_ENGINE = "google_scholar"
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'pz_deep_research.db'}"
LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


VALID_EDITIONS = ("community", "cloud")
DEFAULT_EDITION = "community"


@dataclass(frozen=True)
class Settings:
    app_name: str = "PZ Deep Research API"
    edition: str = DEFAULT_EDITION
    default_provider: str = "mock"
    default_model: str = ""
    model_routing_mode: str = "production"
    production_provider: str = ""
    production_model: str = ""
    model_routing_version: str = DEFAULT_CLOUD_ROUTING_VERSION
    mock_provider_delay_seconds: float = 0.0
    llm_max_retries: int = 3
    llm_retry_base_delay_seconds: float = 2.0
    llm_timeout_seconds: float = 60.0
    openai_api_key: str = ""
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    openai_model: str = ""
    openai_report_model: str = ""
    openai_model_options: tuple[str, ...] = DEFAULT_OPENAI_MODEL_OPTIONS
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    anthropic_model_options: tuple[str, ...] = DEFAULT_ANTHROPIC_MODEL_OPTIONS
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_model_options: tuple[str, ...] = DEFAULT_GEMINI_MODEL_OPTIONS
    search_provider: str = DEFAULT_SEARCH_PROVIDER
    academic_search_engine: str = DEFAULT_ACADEMIC_SEARCH_ENGINE
    serpapi_api_key: str = ""
    jina_api_key: str = ""
    visit_max_concurrency: int = 5
    evidence_extraction_model: str = DEFAULT_OPENAI_EVIDENCE_MODEL
    anthropic_evidence_model: str = DEFAULT_ANTHROPIC_EVIDENCE_MODEL
    gemini_evidence_model: str = DEFAULT_GEMINI_EVIDENCE_MODEL
    database_url: str = DEFAULT_DATABASE_URL
    database_migration_url: str = DEFAULT_DATABASE_URL
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 300
    clerk_jwt_key: str = ""
    clerk_authorized_parties: tuple[str, ...] = LOCAL_FRONTEND_ORIGINS
    clerk_clock_skew_seconds: int = 5
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    pdf_export_timeout_seconds: float = 45.0
    pdf_export_max_concurrency: int = 2
    pdf_chromium_executable_path: str = ""
    # When true (shared / public-demo deployments), a client-supplied BYOK
    # base_url must use https and may not point at private/loopback addresses.
    # Default false keeps local-LLM endpoints (e.g. Ollama at localhost) usable
    # for single-user self-hosting; link-local/metadata is blocked regardless.
    byok_restrict_base_url: bool = False


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str | None
    routing_version: str
    selection_enabled: bool


@dataclass(frozen=True)
class ByokCredentials:
    """Edition-gated bring-your-own-key credentials.

    Cloud edition ignores any client-supplied credentials, so every field is
    ``None`` there. Resolving this in one place keeps the four-field gating from
    drifting across call sites and leaking client keys into the cloud edition.
    """

    api_key: str | None = None
    base_url: str | None = None
    search_api_key: str | None = None
    reader_api_key: str | None = None


class ByokCredentialError(ValueError):
    """Client-supplied BYOK credentials are unsafe or internally inconsistent."""


def validate_byok_base_url(url: str, *, restrict_network: bool) -> None:
    """Reject a client base_url that could be abused for SSRF / key exfiltration.

    A literal IP host is always range-checked (cheap, no DNS), so the
    169.254.169.254 cloud-metadata address and other reserved ranges are blocked
    even by default. ``restrict_network`` (shared / public-demo deployments)
    additionally forces https, resolves hostnames via DNS, and blocks
    private/loopback so the server cannot probe an internal network. It stays off
    by default so single-user self-hosting can point BYOK at a local LLM (e.g.
    Ollama on localhost) with a custom hostname.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    allowed_schemes = ("https",) if restrict_network else ("http", "https")
    if scheme not in allowed_schemes:
        raise ByokCredentialError(
            "base_url 必须使用 https" if restrict_network else "base_url 必须是 http(s) URL"
        )
    host = parsed.hostname
    if not host:
        raise ByokCredentialError("base_url 缺少有效主机名")

    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        # Hostname: only resolve in strict mode (public/shared deployments) so
        # default self-hosting does not depend on DNS or block custom hostnames.
        if not restrict_network:
            return
        try:
            infos = socket.getaddrinfo(host, parsed.port)
        except socket.gaierror as exc:
            raise ByokCredentialError("base_url 主机无法解析") from exc
        candidates = [ipaddress.ip_address(info[4][0]) for info in infos]

    for ip in candidates:
        if ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ByokCredentialError("base_url 指向受限网络地址")
        if restrict_network and (ip.is_private or ip.is_loopback):
            raise ByokCredentialError("base_url 指向内网地址")


def resolve_byok_credentials(settings: Settings, source: object | None) -> ByokCredentials:
    # BYOK is community-only; the cloud edition never honors client credentials.
    if source is None or settings.edition != "community":
        return ByokCredentials()
    api_key = getattr(source, "api_key", None) or None
    base_url = getattr(source, "base_url", None) or None
    # A client base_url must never pair with the server API key: that would send
    # the server key to an attacker-controlled endpoint. Only honor a custom
    # base_url as part of a complete BYOK pair, and validate it for SSRF.
    if base_url and not api_key:
        raise ByokCredentialError("提供自定义 base_url 时必须同时提供 API Key")
    if base_url:
        validate_byok_base_url(base_url, restrict_network=settings.byok_restrict_base_url)
    return ByokCredentials(
        api_key=api_key,
        base_url=base_url,
        search_api_key=getattr(source, "search_api_key", None) or None,
        reader_api_key=getattr(source, "reader_api_key", None) or None,
    )


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_edition() -> str:
    edition = _get_env("PZ_EDITION", DEFAULT_EDITION).lower()
    return edition if edition in VALID_EDITIONS else DEFAULT_EDITION


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


def _get_cors_origins() -> tuple[str, ...]:
    raw = os.getenv("CORS_ORIGINS", LOCAL_FRONTEND_ORIGINS[0])
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if any(origin in LOCAL_FRONTEND_ORIGINS for origin in origins):
        for local_origin in LOCAL_FRONTEND_ORIGINS:
            if local_origin not in origins:
                origins.append(local_origin)
    return tuple(origins) or LOCAL_FRONTEND_ORIGINS


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return database_url


def _get_database_url(name: str, default: str) -> str:
    return _normalize_database_url(_get_env(name, default))


def get_settings() -> Settings:
    return Settings(
        edition=_get_edition(),
        default_provider=_get_env("DEFAULT_PROVIDER", "mock"),
        default_model=_get_env("DEFAULT_MODEL", ""),
        model_routing_mode=_get_env("MODEL_ROUTING_MODE", "production").lower(),
        production_provider=_get_env("PRODUCTION_PROVIDER", "").lower(),
        production_model=_get_env("PRODUCTION_MODEL", ""),
        model_routing_version=_get_env(
            "MODEL_ROUTING_VERSION",
            DEFAULT_CLOUD_ROUTING_VERSION,
        ),
        mock_provider_delay_seconds=_get_float_env("MOCK_PROVIDER_DELAY_SECONDS", 0.0),
        llm_max_retries=_get_int_env("LLM_MAX_RETRIES", 3),
        llm_retry_base_delay_seconds=_get_float_env("LLM_RETRY_BASE_DELAY_SECONDS", 2.0),
        llm_timeout_seconds=_get_float_env("LLM_TIMEOUT_SECONDS", 60.0),
        openai_api_key=_get_env("OPENAI_API_KEY", ""),
        openai_base_url=_get_env("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        openai_model=_get_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        openai_report_model=_get_env("OPENAI_REPORT_MODEL", ""),
        openai_model_options=_get_csv_env("OPENAI_MODEL_OPTIONS", DEFAULT_OPENAI_MODEL_OPTIONS),
        anthropic_api_key=_get_env("ANTHROPIC_API_KEY", ""),
        anthropic_model=_get_env("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        anthropic_model_options=_get_csv_env(
            "ANTHROPIC_MODEL_OPTIONS",
            DEFAULT_ANTHROPIC_MODEL_OPTIONS,
        ),
        gemini_api_key=_get_env("GEMINI_API_KEY", ""),
        gemini_model=_get_env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        gemini_model_options=_get_csv_env(
            "GEMINI_MODEL_OPTIONS",
            DEFAULT_GEMINI_MODEL_OPTIONS,
        ),
        search_provider=_get_env("SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER).lower(),
        academic_search_engine=_get_env("ACADEMIC_SEARCH_ENGINE", DEFAULT_ACADEMIC_SEARCH_ENGINE),
        serpapi_api_key=_get_env("SERPAPI_API_KEY", ""),
        jina_api_key=_get_env("JINA_API_KEY", ""),
        visit_max_concurrency=_get_int_env("VISIT_MAX_CONCURRENCY", 5),
        evidence_extraction_model=_get_env(
            "EVIDENCE_EXTRACTION_MODEL",
            DEFAULT_OPENAI_EVIDENCE_MODEL,
        ),
        anthropic_evidence_model=_get_env(
            "ANTHROPIC_EVIDENCE_MODEL",
            DEFAULT_ANTHROPIC_EVIDENCE_MODEL,
        ),
        gemini_evidence_model=_get_env(
            "GEMINI_EVIDENCE_MODEL",
            DEFAULT_GEMINI_EVIDENCE_MODEL,
        ),
        database_url=_get_database_url("DATABASE_URL", DEFAULT_DATABASE_URL),
        database_migration_url=_get_database_url(
            "DATABASE_MIGRATION_URL",
            _get_env("DATABASE_URL", DEFAULT_DATABASE_URL),
        ),
        database_pool_size=max(1, _get_int_env("DATABASE_POOL_SIZE", 5)),
        database_max_overflow=max(0, _get_int_env("DATABASE_MAX_OVERFLOW", 5)),
        database_pool_timeout_seconds=max(
            1,
            _get_int_env("DATABASE_POOL_TIMEOUT_SECONDS", 30),
        ),
        database_pool_recycle_seconds=max(
            30,
            _get_int_env("DATABASE_POOL_RECYCLE_SECONDS", 300),
        ),
        clerk_jwt_key=_get_env("CLERK_JWT_KEY", ""),
        clerk_authorized_parties=_get_csv_env(
            "CLERK_AUTHORIZED_PARTIES",
            LOCAL_FRONTEND_ORIGINS,
        ),
        clerk_clock_skew_seconds=max(
            0,
            _get_int_env("CLERK_CLOCK_SKEW_SECONDS", 5),
        ),
        cors_origins=_get_cors_origins(),
        pdf_export_timeout_seconds=_get_float_env("PDF_EXPORT_TIMEOUT_SECONDS", 45.0),
        pdf_export_max_concurrency=_get_int_env("PDF_EXPORT_MAX_CONCURRENCY", 2),
        pdf_chromium_executable_path=_get_env("PDF_CHROMIUM_EXECUTABLE_PATH", ""),
        byok_restrict_base_url=_get_bool_env("BYOK_RESTRICT_BASE_URL", False),
    )


def resolve_model_route(
    settings: Settings,
    *,
    requested_provider: str | None = None,
    requested_model: str | None = None,
) -> ModelRoute:
    # Community edition is a single-user, self-hosted tool: the client always
    # picks its own provider/model (and may bring its own API key). Cloud edition
    # keeps versioned production routing and only honors manual mode internally.
    if settings.edition == "community":
        provider = (requested_provider or settings.default_provider).lower()
        return ModelRoute(
            provider=provider,
            model=provider_model(settings, provider, requested_model) or None,
            routing_version="community",
            selection_enabled=True,
        )

    if settings.model_routing_mode == "manual":
        provider = (requested_provider or settings.default_provider).lower()
        return ModelRoute(
            provider=provider,
            model=provider_model(settings, provider, requested_model) or None,
            routing_version="manual",
            selection_enabled=True,
        )

    provider = settings.production_provider.lower()
    return ModelRoute(
        provider=provider,
        model=settings.production_model or provider_model(settings, provider) or None,
        routing_version=settings.model_routing_version,
        selection_enabled=False,
    )


def missing_search_requirements(
    settings: Settings,
    *,
    api_key_override: str | None = None,
) -> list[str]:
    if api_key_override:
        return []
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
    api_key_override: str | None = None,
    search_api_key_override: str | None = None,
) -> list[str]:
    normalized = provider.lower()
    missing: list[str] = []
    if normalized == "mock":
        return missing
    # A BYOK key (community edition) satisfies the provider key requirement.
    has_user_key = bool(api_key_override)
    if normalized == "openai" and not (settings.openai_api_key or has_user_key):
        missing.append("OPENAI_API_KEY")
    elif normalized == "anthropic" and not (settings.anthropic_api_key or has_user_key):
        missing.append("ANTHROPIC_API_KEY")
    elif normalized == "gemini" and not (settings.gemini_api_key or has_user_key):
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
        missing.extend(
            missing_search_requirements(
                settings,
                api_key_override=search_api_key_override,
            )
        )
    return missing
