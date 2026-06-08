from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchEvent, ResearchRequest
from app.agent.tools import build_default_tool_registry
from app.config import Settings
from app.main import app
from app.storage import InMemoryJobStore


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_returns_provider_and_tool_status() -> None:
    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert "providers" in payload
    assert "openai" in payload["providers"]
    assert "tools" in payload
    assert "search" in payload["tools"]


def test_model_options_endpoint_returns_openai_candidates() -> None:
    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    openai_models = [item["id"] for item in payload["providers"]["openai"]]
    assert "gpt-5.5" in openai_models
    assert "gpt-5.4-mini" in openai_models


def test_openai_available_models_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "settings",
        Settings(openai_api_key="", openai_model="gpt-5.4-mini"),
    )

    response = client.get("/api/models/openai")

    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]["missing"]


def test_create_mock_research_job(monkeypatch) -> None:
    # 用离线 mock 搜索的 runtime，避免 BackgroundTasks 在 TestClient 内同步跑真实 SerpAPI/Jina。
    mock_settings = Settings(default_provider="mock", search_provider="mock")
    monkeypatch.setattr(
        routes,
        "runtime",
        AgentRuntime(
            provider_factory=ProviderFactory(mock_settings),
            tool_registry=build_default_tool_registry(mock_settings),
        ),
    )
    response = client.post(
        "/api/research-jobs",
        json={
            "query": "测试 API 创建研究任务",
            "mode": "quick",
            "provider": "mock",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "测试 API 创建研究任务"
    assert payload["mode"] == "quick"
    assert payload["provider"] == "mock"
    assert payload["status"] in {"queued", "running", "completed"}


def test_research_job_validation_rejects_short_query() -> None:
    response = client.post(
        "/api/research-jobs",
        json={
            "query": "",
            "mode": "quick",
            "provider": "mock",
        },
    )

    assert response.status_code == 422


def test_run_research_job_does_not_persist_stream_deltas(monkeypatch) -> None:
    class DeltaRuntime:
        async def run(self, job_id: str, request: ResearchRequest):
            yield ResearchEvent(
                job_id=job_id,
                type="llm_delta",
                message="模型流式输出",
                payload={"delta": "token"},
            )
            yield ResearchEvent(
                job_id=job_id,
                type="report_delta",
                message="报告流式输出",
                payload={"delta": "报告片段"},
            )
            yield ResearchEvent(
                job_id=job_id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )

    async def run_job():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试 delta 历史存储", mode="quick", provider="mock")
        job = await store.create_job(request, provider="mock")
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", DeltaRuntime())

        await routes.run_research_job(job.id, request)
        return await store.list_events(job.id)

    import asyncio

    events = asyncio.run(run_job())
    event_types = [event.type for event in events]

    assert event_types == ["completed"]
