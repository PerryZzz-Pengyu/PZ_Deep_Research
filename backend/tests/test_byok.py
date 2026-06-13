from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agent.providers import ProviderFactory
from app.agent.providers.base import LLMProvider
from app.agent.providers.mock_provider import MockProvider
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchRequest
from app.agent.tools import build_default_tool_registry
from app.api import routes
from app.config import Settings
from app.main import app
from app.storage import InMemoryJobStore

client = TestClient(app)
VISITOR_HEADERS = {"X-PZ-Visitor-ID": "33333333-3333-4333-8333-333333333333"}

USER_KEY = "sk-user-byok-secret-1234567890"


class SpyFactory(ProviderFactory):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.calls: list[tuple[str | None, str | None, str | None]] = []

    def create(
        self,
        provider_name: str | None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMProvider:
        self.calls.append((provider_name, api_key, base_url))
        return MockProvider()


def test_factory_create_uses_byok_override() -> None:
    settings = Settings(openai_api_key="server-key", openai_model="gpt-5.4-mini")
    factory = ProviderFactory(settings)

    provider = factory.create("openai", api_key=USER_KEY, base_url="https://proxy.example/v1")

    assert provider.api_key == USER_KEY
    assert provider.base_url == "https://proxy.example/v1"


def test_factory_create_falls_back_to_settings_without_override() -> None:
    settings = Settings(openai_api_key="server-key", openai_model="gpt-5.4-mini")
    factory = ProviderFactory(settings)

    provider = factory.create("openai")

    assert provider.api_key == "server-key"


def test_research_request_excludes_credentials_from_serialization() -> None:
    request = ResearchRequest(
        query="保密测试",
        mode="quick",
        provider="openai",
        api_key=USER_KEY,
        base_url="https://proxy.example/v1",
    )

    dumped = request.model_dump()
    assert "api_key" not in dumped
    assert "base_url" not in dumped
    assert USER_KEY not in request.model_dump_json()


def test_runtime_forwards_byok_credentials_to_factory() -> None:
    settings = Settings(default_provider="mock")
    spy = SpyFactory(settings)

    async def run_runtime() -> None:
        runtime = AgentRuntime(
            provider_factory=spy,
            tool_registry=build_default_tool_registry(settings),
        )
        request = ResearchRequest(
            query="测试 BYOK 透传",
            mode="quick",
            provider="mock",
            api_key=USER_KEY,
        )
        async for _ in runtime.run("byok-job", request):
            pass

    asyncio.run(run_runtime())

    assert spy.calls, "ProviderFactory.create was never called"
    assert any(call[1] == USER_KEY for call in spy.calls)


def _capture_run_job():
    captured: dict[str, ResearchRequest] = {}

    async def run_job(job_id: str, request: ResearchRequest, retry_context=None) -> None:
        captured["request"] = request

    return captured, run_job


def test_community_create_job_forwards_byok_and_does_not_persist(monkeypatch) -> None:
    community_settings = Settings(
        edition="community",
        default_provider="mock",
        serpapi_api_key="test-serpapi-key",
    )
    store = InMemoryJobStore()
    captured, run_job = _capture_run_job()
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "社区版自带 Key 应当被透传",
            "mode": "quick",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "api_key": USER_KEY,
            "base_url": "https://proxy.example/v1",
        },
    )

    assert response.status_code == 200, response.text
    # The user key reaches the background task in memory ...
    assert captured["request"].api_key == USER_KEY
    assert captured["request"].provider == "anthropic"
    # ... but never the response body or the persisted job.
    assert USER_KEY not in response.text
    asyncio.run(_assert_store_has_no_secret(store))


async def _assert_store_has_no_secret(store: InMemoryJobStore) -> None:
    jobs = await store.list_jobs(anonymous_id="33333333-3333-4333-8333-333333333333")
    assert jobs, "expected the created job to be persisted"
    for job in jobs:
        assert USER_KEY not in job.model_dump_json()


def test_cloud_create_job_ignores_byok(monkeypatch) -> None:
    cloud_settings = Settings(
        edition="cloud",
        model_routing_mode="production",
        production_provider="openai",
        production_model="gpt-5.4-mini",
        model_routing_version="openai-default-v1",
        openai_api_key="server-key",
        serpapi_api_key="test-serpapi-key",
    )
    captured, run_job = _capture_run_job()
    monkeypatch.setattr(routes, "settings", cloud_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "云端版必须忽略客户端 Key",
            "mode": "quick",
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "api_key": USER_KEY,
        },
    )

    assert response.status_code == 200, response.text
    assert captured["request"].api_key is None
    assert captured["request"].provider == "openai"
    assert captured["request"].model == "gpt-5.4-mini"


def test_community_byok_allows_creation_without_server_key(monkeypatch) -> None:
    # Community host has no server OpenAI key; the user supplies their own.
    community_settings = Settings(
        edition="community",
        default_provider="mock",
        openai_api_key="",
        serpapi_api_key="test-serpapi-key",
    )
    captured, run_job = _capture_run_job()
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "无服务端 Key 时社区版应接受自带 Key",
            "mode": "quick",
            "provider": "openai",
            "model": "gpt-5.4-mini",
            "api_key": USER_KEY,
        },
    )

    assert response.status_code == 200, response.text
    assert captured["request"].api_key == USER_KEY
