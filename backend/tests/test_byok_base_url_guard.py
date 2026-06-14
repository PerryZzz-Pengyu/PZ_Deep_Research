"""Regression tests for the BYOK base_url / server-key exfiltration fix.

A community client could previously send a custom ``base_url`` without an
``api_key``; the factory then paired the attacker URL with the *server* API key
and leaked it. The fix requires a client base_url to travel with a client key,
validates the URL against SSRF targets, and rejects the unsafe combination with
a 400.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent.providers import ProviderFactory
from app.agent.schemas import ResearchCredentials
from app.api import routes
from app.config import (
    ByokCredentialError,
    Settings,
    resolve_byok_credentials,
    validate_byok_base_url,
)
from app.main import app

client = TestClient(app)
VISITOR_HEADERS = {"X-PZ-Visitor-ID": "44444444-4444-4444-8444-444444444444"}
USER_KEY = "sk-user-byok-secret-1234567890"
SERVER_KEY = "sk-server-should-never-leak"


def _community(**overrides) -> Settings:
    base = dict(edition="community", default_provider="mock", serpapi_api_key="test-serpapi-key")
    base.update(overrides)
    return Settings(**base)


# --- factory safety net -----------------------------------------------------


def test_factory_drops_client_base_url_without_api_key() -> None:
    # The dangerous combination: client base_url, no client key. The server key
    # must NOT be sent to the client-supplied endpoint.
    settings = Settings(
        openai_api_key=SERVER_KEY,
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-5.4-mini",
    )
    factory = ProviderFactory(settings)

    provider = factory.create("openai", base_url="https://attacker.example/v1")

    assert provider.api_key == SERVER_KEY
    assert provider.base_url == "https://api.openai.com/v1"  # not the attacker URL


def test_factory_keeps_base_url_when_paired_with_key() -> None:
    settings = Settings(openai_api_key=SERVER_KEY, openai_model="gpt-5.4-mini")
    factory = ProviderFactory(settings)

    provider = factory.create("openai", api_key=USER_KEY, base_url="https://proxy.example/v1")

    assert provider.api_key == USER_KEY
    assert provider.base_url == "https://proxy.example/v1"


# --- resolve_byok_credentials gating ----------------------------------------


def test_resolve_rejects_base_url_without_api_key() -> None:
    settings = _community()
    creds = ResearchCredentials(base_url="https://attacker.example/v1")

    with pytest.raises(ByokCredentialError):
        resolve_byok_credentials(settings, creds)


def test_resolve_accepts_paired_public_base_url() -> None:
    settings = _community()
    creds = ResearchCredentials(api_key=USER_KEY, base_url="https://proxy.example/v1")

    resolved = resolve_byok_credentials(settings, creds)

    assert resolved.api_key == USER_KEY
    assert resolved.base_url == "https://proxy.example/v1"


# --- validate_byok_base_url (SSRF) ------------------------------------------


def test_metadata_address_blocked_even_in_permissive_mode() -> None:
    with pytest.raises(ByokCredentialError):
        validate_byok_base_url("http://169.254.169.254/latest/meta-data/", restrict_network=False)


def test_local_llm_endpoint_allowed_in_permissive_mode() -> None:
    # A self-hoster pointing BYOK at a local model (e.g. Ollama) stays usable.
    validate_byok_base_url("http://127.0.0.1:11434/v1", restrict_network=False)


def test_strict_mode_blocks_loopback() -> None:
    with pytest.raises(ByokCredentialError):
        validate_byok_base_url("https://127.0.0.1:11434/v1", restrict_network=True)


def test_strict_mode_requires_https() -> None:
    # 1.1.1.1 is globally routable, so only the scheme should fail here.
    with pytest.raises(ByokCredentialError):
        validate_byok_base_url("http://1.1.1.1/v1", restrict_network=True)


# --- end-to-end API rejection -----------------------------------------------


def test_community_create_rejects_base_url_without_key(monkeypatch) -> None:
    monkeypatch.setattr(routes, "settings", _community(openai_api_key=SERVER_KEY))

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "缺少 Key 的自定义 base_url 必须被拒绝",
            "mode": "quick",
            "provider": "openai",
            "model": "gpt-5.4-mini",
            "base_url": "https://attacker.example/v1",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "invalid_byok_credentials"
    assert SERVER_KEY not in response.text
