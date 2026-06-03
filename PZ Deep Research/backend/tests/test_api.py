from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.config import Settings
from app.main import app


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


def test_create_mock_research_job() -> None:
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
