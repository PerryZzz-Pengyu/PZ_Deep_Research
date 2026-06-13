from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agent.providers import ProviderFactory
from app.agent.providers.base import LLMProvider
from app.agent.providers.mock_provider import MockProvider
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchEvent, ResearchRequest
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
        search_api_key="serpapi-user-secret",
        reader_api_key="jina-user-secret",
    )

    dumped = request.model_dump()
    assert "api_key" not in dumped
    assert "base_url" not in dumped
    assert "search_api_key" not in dumped
    assert "reader_api_key" not in dumped
    assert USER_KEY not in request.model_dump_json()
    assert "serpapi-user-secret" not in request.model_dump_json()
    assert "jina-user-secret" not in request.model_dump_json()


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


def test_community_create_job_forwards_tool_credentials(monkeypatch) -> None:
    community_settings = Settings(
        edition="community",
        default_provider="mock",
        openai_api_key="",
        search_provider="mock",
        serpapi_api_key="",
    )
    captured, run_job = _capture_run_job()
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "社区版按请求透传模型、搜索和阅读凭据",
            "mode": "quick",
            "provider": "openai",
            "model": "gpt-5.4-mini",
            "api_key": USER_KEY,
            "search_api_key": "serpapi-user-secret",
            "reader_api_key": "jina-user-secret",
        },
    )

    assert response.status_code == 200, response.text
    request = captured["request"]
    assert request.api_key == USER_KEY
    assert request.search_api_key == "serpapi-user-secret"
    assert request.reader_api_key == "jina-user-secret"
    assert "serpapi-user-secret" not in response.text
    assert "jina-user-secret" not in response.text


def test_community_rerun_accepts_fresh_byok_credentials(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        original = await store.create_job(
            ResearchRequest(
                query="BYOK 任务需要重新输入凭据后重跑",
                mode="quick",
                provider="openai",
                model="gpt-5.4-mini",
            ),
            provider="openai",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
            routing_version="community",
        )
        await store.add_event(
            ResearchEvent(
                job_id=original.id,
                type="completed",
                message="完成",
                payload={"final_report": "完成", "sources": []},
            )
        )
        return store, original

    community_settings = Settings(
        edition="community",
        openai_api_key="",
        search_provider="mock",
    )
    captured, run_job = _capture_run_job()
    store, original = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        f"/api/research-jobs/{original.id}/rerun",
        headers=VISITOR_HEADERS,
        json={
            "api_key": USER_KEY,
            "search_api_key": "serpapi-rerun-secret",
            "reader_api_key": "jina-rerun-secret",
        },
    )

    assert response.status_code == 200, response.text
    request = captured["request"]
    assert request.api_key == USER_KEY
    assert request.search_api_key == "serpapi-rerun-secret"
    assert request.reader_api_key == "jina-rerun-secret"


def test_cloud_rerun_ignores_client_credentials(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        original = await store.create_job(
            ResearchRequest(
                query="云端重跑必须忽略客户端凭据",
                mode="quick",
                provider="openai",
                model="cloud-model",
            ),
            provider="openai",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
            routing_version="cloud-route",
        )
        await store.add_event(
            ResearchEvent(
                job_id=original.id,
                type="completed",
                message="完成",
                payload={"final_report": "完成", "sources": []},
            )
        )
        return store, original

    cloud_settings = Settings(
        edition="cloud",
        openai_api_key="server-key",
        openai_model="cloud-model",
        search_provider="mock",
    )
    captured, run_job = _capture_run_job()
    store, original = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "settings", cloud_settings)
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        f"/api/research-jobs/{original.id}/rerun",
        headers=VISITOR_HEADERS,
        json={
            "api_key": USER_KEY,
            "search_api_key": "serpapi-client-secret",
            "reader_api_key": "jina-client-secret",
        },
    )

    assert response.status_code == 200, response.text
    request = captured["request"]
    assert request.api_key is None
    assert request.search_api_key is None
    assert request.reader_api_key is None


def test_community_retry_accepts_fresh_byok_credentials(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        original = await store.create_job(
            ResearchRequest(
                query="BYOK 失败任务需要重新输入凭据后重试",
                mode="quick",
                provider="openai",
                model="gpt-5.4-mini",
            ),
            provider="openai",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
            routing_version="community",
        )
        await store.add_event(
            ResearchEvent(
                job_id=original.id,
                type="failed",
                message="上游服务暂时不可用",
                payload={
                    "error_code": "service_unavailable",
                    "retryable": True,
                    "stage": "search",
                },
            )
        )
        return store, original

    community_settings = Settings(
        edition="community",
        openai_api_key="",
        search_provider="mock",
    )
    captured, run_job = _capture_run_job()
    store, original = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", run_job)

    response = client.post(
        f"/api/research-jobs/{original.id}/retry",
        headers=VISITOR_HEADERS,
        json={
            "api_key": USER_KEY,
            "search_api_key": "serpapi-retry-secret",
            "reader_api_key": "jina-retry-secret",
        },
    )

    assert response.status_code == 200, response.text
    request = captured["request"]
    assert request.api_key == USER_KEY
    assert request.search_api_key == "serpapi-retry-secret"
    assert request.reader_api_key == "jina-retry-secret"
