from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.api import routes
from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchEvent, ResearchRequest
from app.agent.tools import build_default_tool_registry
from app.auth import ClerkAuthenticator, RequestIdentity
from app.config import Settings
from app.main import app
from app.storage import InMemoryJobStore


client = TestClient(app)
VISITOR_HEADERS = {"X-PZ-Visitor-ID": "11111111-1111-4111-8111-111111111111"}
OTHER_VISITOR_HEADERS = {"X-PZ-Visitor-ID": "22222222-2222-4222-8222-222222222222"}


def auth_fixture(user_id: str) -> tuple[ClerkAuthenticator, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user_id,
            "sid": f"session-{user_id}",
            "azp": "http://localhost:3000",
            "iat": now,
            "nbf": now - timedelta(seconds=1),
            "exp": now + timedelta(minutes=5),
        },
        private_pem,
        algorithm="RS256",
    )
    return (
        ClerkAuthenticator(
            jwt_key=public_pem,
            authorized_parties=("http://localhost:3000",),
        ),
        {
            **VISITOR_HEADERS,
            "Authorization": f"Bearer {token}",
        },
    )


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
    assert payload["edition"] in {"community", "cloud"}


def test_model_options_endpoint_returns_provider_candidates(monkeypatch) -> None:
    # Pin a configured cloud edition so the assertion does not depend on the
    # ambient .env (CI has none → community default → selection enabled).
    monkeypatch.setattr(
        routes,
        "settings",
        Settings(
            edition="cloud",
            model_routing_mode="production",
            production_provider="openai",
            production_model="gpt-5.4-mini",
            model_routing_version="openai-default-v1",
        ),
    )

    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_enabled"] is False
    assert payload["routing_version"] == "openai-default-v1"
    openai_models = [item["id"] for item in payload["providers"]["openai"]]
    anthropic_models = [item["id"] for item in payload["providers"]["anthropic"]]
    gemini_models = [item["id"] for item in payload["providers"]["gemini"]]
    assert "gpt-5.5" in openai_models
    assert "gpt-5.4-mini" in openai_models
    assert "claude-opus-4-8" in anthropic_models
    assert "claude-sonnet-4-6" in anthropic_models
    assert "gemini-3.5-flash" in gemini_models
    assert "gemini-3.1-pro-preview" in gemini_models


def test_create_research_job_uses_production_route(monkeypatch) -> None:
    async def do_not_run_job(job_id: str, request: ResearchRequest) -> None:
        return None

    production_settings = Settings(
        edition="cloud",
        model_routing_mode="production",
        production_provider="openai",
        production_model="gpt-5.4-mini",
        model_routing_version="openai-default-v1",
        openai_api_key="test-openai-key",
        serpapi_api_key="test-serpapi-key",
    )
    monkeypatch.setattr(routes, "settings", production_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
    monkeypatch.setattr(routes, "run_research_job", do_not_run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "生产路由必须由后端决定",
            "mode": "quick",
            "provider": "anthropic",
            "model": "claude-opus-4-8",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["routing_version"] == "openai-default-v1"


def test_create_research_job_community_edition_honors_client_provider(monkeypatch) -> None:
    async def do_not_run_job(job_id: str, request: ResearchRequest) -> None:
        return None

    community_settings = Settings(
        edition="community",
        default_provider="mock",
        anthropic_api_key="user-supplied-not-needed-here",
        serpapi_api_key="test-serpapi-key",
    )
    monkeypatch.setattr(routes, "settings", community_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
    monkeypatch.setattr(routes, "run_research_job", do_not_run_job)

    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
        json={
            "query": "社区版应当尊重客户端选择",
            "mode": "quick",
            "provider": "anthropic",
            "model": "claude-opus-4-8",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-opus-4-8"
    assert payload["routing_version"] == "community"


def test_openai_available_models_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "settings",
        Settings(openai_api_key="", openai_model="gpt-5.4-mini"),
    )

    response = client.get("/api/models/openai")

    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]["missing"]


def test_anthropic_available_models_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "settings",
        Settings(anthropic_api_key="", anthropic_model="claude-sonnet-4-6"),
    )

    response = client.get("/api/models/anthropic")

    assert response.status_code == 400
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]["missing"]


def test_gemini_available_models_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "settings",
        Settings(gemini_api_key="", gemini_model="gemini-3.5-flash"),
    )

    response = client.get("/api/models/gemini")

    assert response.status_code == 400
    assert "GEMINI_API_KEY" in response.json()["detail"]["missing"]


def test_create_mock_research_job(monkeypatch) -> None:
    # 用离线 mock 搜索的 runtime，避免 BackgroundTasks 在 TestClient 内同步跑真实 SerpAPI/Jina。
    mock_settings = Settings(
        model_routing_mode="manual",
        default_provider="mock",
        search_provider="mock",
    )
    monkeypatch.setattr(routes, "settings", mock_settings)
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())
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
        headers=VISITOR_HEADERS,
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

    # The job runner records usage as it streams; a completed mock run must have
    # logged at least one LLM call and one tool call.
    usage = client.get("/api/usage", headers=VISITOR_HEADERS).json()
    assert usage["llm_calls"] >= 1
    assert usage["tool_calls"] >= 1
    assert usage["job_count"] == 1


def test_usage_endpoint_returns_owner_scoped_totals(monkeypatch) -> None:
    store = InMemoryJobStore()

    async def seed():
        request = ResearchRequest(query="用量端点测试", mode="quick", provider="mock")
        job_a = await store.create_job(
            request, provider="mock", anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"]
        )
        await store.record_usage(
            job_a.id, input_tokens=120, output_tokens=30, llm_calls=2, tool_calls=4
        )
        other = await store.create_job(
            request, provider="mock", anonymous_id=OTHER_VISITOR_HEADERS["X-PZ-Visitor-ID"]
        )
        await store.record_usage(
            other.id, input_tokens=777, output_tokens=777, llm_calls=7, tool_calls=7
        )

    asyncio.run(seed())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.get("/api/usage", headers=VISITOR_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "input_tokens": 120,
        "output_tokens": 30,
        "llm_calls": 2,
        "tool_calls": 4,
        "job_count": 1,
    }


def test_usage_endpoint_excludes_cost_and_pricing(monkeypatch) -> None:
    # Open-core boundary: the public usage endpoint exposes raw counts only.
    # Cost/price computation is a private Cloud concern.
    monkeypatch.setattr(routes, "job_store", InMemoryJobStore())

    response = client.get("/api/usage", headers=VISITOR_HEADERS)

    assert response.status_code == 200
    body = response.text.lower()
    assert "cost" not in body
    assert "price" not in body
    assert "usd" not in body


def test_research_job_validation_rejects_short_query() -> None:
    response = client.post(
        "/api/research-jobs",
        headers=VISITOR_HEADERS,
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
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", DeltaRuntime())

        await routes.run_research_job(job.id, request)
        return await store.list_events(job.id)

    import asyncio

    events = asyncio.run(run_job())
    event_types = [event.type for event in events]

    assert event_types == ["completed"]


def test_run_research_job_sanitizes_failed_events(monkeypatch) -> None:
    class FailingRuntime:
        async def run(self, job_id: str, request: ResearchRequest):
            yield ResearchEvent(
                job_id=job_id,
                type="failed",
                message="研究任务失败：401 invalid api key sk-secret-value",
                payload={
                    "provider": "openai",
                    "error": "401 invalid api key sk-secret-value",
                    "stage": "report",
                },
            )

    async def run_job():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试错误脱敏", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", FailingRuntime())

        await routes.run_research_job(job.id, request)
        return await store.get_job(job.id), await store.list_events(job.id)

    job, events = asyncio.run(run_job())

    assert job is not None
    assert job.status == "failed"
    assert job.error_code == "service_unavailable"
    assert job.error_retryable is False
    assert "sk-secret-value" not in (job.error or "")
    assert "sk-secret-value" not in str(events[0].payload)


def test_job_store_tracks_report_draft_without_persisting_delta_events() -> None:
    async def run_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试刷新恢复报告草稿", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.append_report_delta(job.id, "第一段")
        await store.append_report_delta(job.id, "第二段")
        before_reset = await store.get_job(job.id)
        events_before_reset = await store.list_events(job.id)
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="report_reset",
                message="报告草稿重置",
            )
        )
        after_reset = await store.get_job(job.id)
        return before_reset, events_before_reset, after_reset

    before_reset, events_before_reset, after_reset = asyncio.run(run_store())

    assert before_reset is not None
    assert before_reset.draft_report == "第一段第二段"
    assert events_before_reset == []
    assert after_reset is not None
    assert after_reset.draft_report == ""


def test_cancel_endpoint_marks_running_job_and_records_event(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试取消接口", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        assert await store.start_job(job.id) is True
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.post(f"/api/research-jobs/{job.id}/cancel", headers=VISITOR_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    events = asyncio.run(store.list_events(job.id))
    assert [event.type for event in events] == ["cancelled"]

    second_response = client.post(f"/api/research-jobs/{job.id}/cancel", headers=VISITOR_HEADERS)
    assert second_response.status_code == 200
    assert len(asyncio.run(store.list_events(job.id))) == 1


def test_cancel_endpoint_rejects_completed_job(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试已完成任务不能取消", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.post(f"/api/research-jobs/{job.id}/cancel", headers=VISITOR_HEADERS)

    assert response.status_code == 409
    assert response.json()["detail"] == "任务已经结束，无法取消"


def test_cancel_endpoint_interrupts_running_background_coroutine(monkeypatch) -> None:
    class BlockingRuntime:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.blocker = asyncio.Event()

        async def run(self, job_id: str, request: ResearchRequest):
            self.started.set()
            yield ResearchEvent(job_id=job_id, type="status", message="已开始")
            await self.blocker.wait()
            yield ResearchEvent(
                job_id=job_id,
                type="completed",
                message="不应该完成",
                payload={"final_report": "不应该出现", "sources": []},
            )

    async def run_scenario():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试取消后台任务", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        runtime = BlockingRuntime()
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", runtime)
        routes.running_tasks.clear()

        task = asyncio.create_task(routes.run_research_job(job.id, request))
        await asyncio.wait_for(runtime.started.wait(), timeout=1)
        cancelled_job = await routes.cancel_research_job(
            job.id,
            RequestIdentity(
                anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
                user_id=None,
            ),
        )
        await asyncio.wait_for(task, timeout=1)
        return cancelled_job, await store.get_job(job.id), await store.list_events(job.id)

    cancelled_job, stored_job, events = asyncio.run(run_scenario())

    assert cancelled_job.status == "cancelled"
    assert stored_job is not None
    assert stored_job.status == "cancelled"
    assert [event.type for event in events] == ["status", "cancelled"]
    assert all(event.type != "completed" for event in events)


def test_sse_resume_replays_only_events_after_cursor_and_includes_snapshot(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试 SSE 续接", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        first = ResearchEvent(job_id=job.id, type="status", message="第一步")
        second = ResearchEvent(
            job_id=job.id,
            type="completed",
            message="研究报告已生成",
            payload={"final_report": "恢复后的完整报告", "sources": []},
        )
        await store.add_event(first)
        await store.add_event(second)
        return store, job, first, second

    store, job, first, second = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.get(
        f"/api/research-jobs/{job.id}/stream?after={first.id}&visitor_id={VISITOR_HEADERS['X-PZ-Visitor-ID']}"
    )

    assert response.status_code == 200
    assert '"type": "job_snapshot"' in response.text
    assert '"final_report": "恢复后的完整报告"' in response.text
    assert f"id: {first.id}" not in response.text
    assert f"id: {second.id}" in response.text


def test_history_endpoint_returns_only_current_visitors_jobs(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request_a = ResearchRequest(query="访客 A 的历史", mode="quick", provider="mock")
        request_b = ResearchRequest(query="访客 B 的历史", mode="deep", provider="mock")
        job_a = await store.create_job(
            request_a,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.create_job(
            request_b,
            provider="mock",
            anonymous_id=OTHER_VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        return store, job_a

    store, job_a = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.get("/api/research-jobs", headers=VISITOR_HEADERS)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [job_a.id]


def test_authenticated_history_claims_current_anonymous_jobs(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="登录后归并的历史", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    authenticator, headers = auth_fixture("user_123")
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "authenticator", authenticator)

    response = client.get("/api/research-jobs", headers=headers)
    anonymous_response = client.get("/api/research-jobs", headers=VISITOR_HEADERS)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [job.id]
    assert anonymous_response.status_code == 200
    assert anonymous_response.json() == []


def test_authenticated_users_cannot_read_each_others_jobs(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="账号 A 的任务", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id="unused",
            user_id="user_a",
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    authenticator, headers = auth_fixture("user_b")
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "authenticator", authenticator)

    response = client.get(f"/api/research-jobs/{job.id}", headers=headers)

    assert response.status_code == 404


def test_job_detail_is_hidden_from_other_visitors(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="仅当前访客可见", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    own_response = client.get(f"/api/research-jobs/{job.id}", headers=VISITOR_HEADERS)
    other_response = client.get(f"/api/research-jobs/{job.id}", headers=OTHER_VISITOR_HEADERS)

    assert own_response.status_code == 200
    assert other_response.status_code == 404


def test_rerun_endpoint_copies_terminal_job_and_records_lineage(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(
            query="重新运行时保留原始研究配置",
            mode="deep",
            provider="mock",
        )
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "原始报告", "sources": []},
            )
        )
        return store, job

    async def do_not_run_job(job_id: str, request: ResearchRequest) -> None:
        return None

    store, original_job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", do_not_run_job)

    response = client.post(
        f"/api/research-jobs/{original_job.id}/rerun",
        headers=VISITOR_HEADERS,
    )

    assert response.status_code == 200
    rerun_job = response.json()
    assert rerun_job["id"] != original_job.id
    assert rerun_job["query"] == original_job.query
    assert rerun_job["mode"] == original_job.mode
    assert rerun_job["provider"] == original_job.provider
    assert rerun_job["model"] == original_job.model
    assert rerun_job["status"] == "queued"
    assert rerun_job["rerun_of_job_id"] == original_job.id


def test_rerun_endpoint_rejects_active_job(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="运行中的任务不能重复重跑", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        assert await store.start_job(job.id) is True
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.post(f"/api/research-jobs/{job.id}/rerun", headers=VISITOR_HEADERS)

    assert response.status_code == 409
    assert response.json()["detail"] == "任务仍在运行，无法重新运行"


def test_rerun_endpoint_hides_other_visitors_job(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="其他访客不能重新运行", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.post(
        f"/api/research-jobs/{job.id}/rerun",
        headers=OTHER_VISITOR_HEADERS,
    )

    assert response.status_code == 404


def test_retry_endpoint_resumes_report_from_saved_evidence(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="从证据继续报告", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        context = {
            "mode": "quick",
            "sources": [{"citation_id": "1", "title": "来源", "url": "https://example.com"}],
            "cards": [
                {
                    "citation_id": "1",
                    "title": "来源",
                    "url": "https://example.com",
                    "evidence_level": "full_text",
                    "content": "证据",
                    "extraction_status": "extracted",
                }
            ],
            "selection": {
                "target": 3,
                "minimum_full_text": 1,
                "total_available": 1,
                "full_text_count": 1,
                "degraded": True,
                "full_text_shortfall": False,
            },
        }
        await store.save_retry_context(job.id, context)
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="failed",
                message="本次研究未能在规定时间内完成，请重试。",
                payload={
                    "error_code": "task_timeout",
                    "retryable": True,
                    "stage": "report",
                },
            )
        )
        return store, job, context

    calls = []

    async def capture_run(job_id, request, retry_context=None):
        calls.append((job_id, request, retry_context))

    store, original_job, context = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "run_research_job", capture_run)

    response = client.post(
        f"/api/research-jobs/{original_job.id}/retry",
        headers=VISITOR_HEADERS,
    )

    assert response.status_code == 200
    retry_job = response.json()
    assert retry_job["id"] != original_job.id
    assert retry_job["rerun_of_job_id"] == original_job.id
    assert calls[0][0] == retry_job["id"]
    assert calls[0][2] == context


def test_retry_endpoint_rejects_non_retryable_failure(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="不可重试错误", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="failed",
                message="研究服务暂时不可用。",
                payload={
                    "error_code": "service_unavailable",
                    "retryable": False,
                    "stage": "search",
                },
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.post(f"/api/research-jobs/{job.id}/retry", headers=VISITOR_HEADERS)

    assert response.status_code == 409
    assert response.json()["detail"] == "当前失败不可直接重试，请重新发起研究"


def test_pdf_export_returns_owned_report_as_attachment(monkeypatch) -> None:
    class FakePdfExporter:
        def __init__(self) -> None:
            self.calls = []

        async def render(self, job, report: str) -> bytes:
            self.calls.append((job, report))
            return b"%PDF-1.7\nmock pdf\n%%EOF"

    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(
            query="PDF 导出 / 文件名",
            mode="deep",
            provider="mock",
        )
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "# PDF 报告\n\n正文", "sources": []},
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    exporter = FakePdfExporter()
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "pdf_exporter", exporter)

    response = client.get(
        f"/api/research-jobs/{job.id}/export/pdf",
        headers=VISITOR_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert "filename*=UTF-8''PDF-%E5%AF%BC%E5%87%BA-%E6%96%87%E4%BB%B6%E5%90%8D.pdf" in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF-")
    assert exporter.calls[0][0].id == job.id
    assert exporter.calls[0][1] == "# PDF 报告\n\n正文"


def test_pdf_export_rejects_empty_report(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="没有报告不能导出", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.get(
        f"/api/research-jobs/{job.id}/export/pdf",
        headers=VISITOR_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "报告尚未生成，无法导出 PDF"


def test_pdf_export_hides_other_visitors_job(monkeypatch) -> None:
    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="PDF 归属隔离", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "私有报告", "sources": []},
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)

    response = client.get(
        f"/api/research-jobs/{job.id}/export/pdf",
        headers=OTHER_VISITOR_HEADERS,
    )

    assert response.status_code == 404


def test_pdf_export_returns_service_unavailable_when_renderer_fails(monkeypatch) -> None:
    class FailingPdfExporter:
        async def render(self, job, report: str) -> bytes:
            raise routes.PdfExportError("Chromium 启动失败")

    async def prepare_store():
        store = InMemoryJobStore()
        request = ResearchRequest(query="PDF 失败提示", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.add_event(
            ResearchEvent(
                job_id=job.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "可导出的报告", "sources": []},
            )
        )
        return store, job

    store, job = asyncio.run(prepare_store())
    monkeypatch.setattr(routes, "job_store", store)
    monkeypatch.setattr(routes, "pdf_exporter", FailingPdfExporter())

    response = client.get(
        f"/api/research-jobs/{job.id}/export/pdf",
        headers=VISITOR_HEADERS,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "PDF 生成失败，请稍后重试"


def test_report_delta_batches_db_writes(monkeypatch) -> None:
    """append_report_delta must NOT be called per-delta; final draft_report must be correct."""

    MANY_DELTAS = 60  # well above the flush threshold (500 chars at ~10 chars each = 600 > 500)

    class ManyDeltaRuntime:
        async def run(self, job_id: str, request: ResearchRequest):
            for i in range(MANY_DELTAS):
                yield ResearchEvent(
                    job_id=job_id,
                    type="report_delta",
                    message="报告流式输出",
                    payload={"delta": f"片段{i:03d}"},
                )
            yield ResearchEvent(
                job_id=job_id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )

    class CountingStore(InMemoryJobStore):
        def __init__(self) -> None:
            super().__init__()
            self.append_calls = 0
            self.appended_content = ""

        async def append_report_delta(self, job_id: str, delta: str) -> None:
            self.append_calls += 1
            self.appended_content += delta
            await super().append_report_delta(job_id, delta)

    async def run_job():
        store = CountingStore()
        request = ResearchRequest(query="测试 delta 合批写入", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", ManyDeltaRuntime())
        await routes.run_research_job(job.id, request)
        return store.append_calls, store.appended_content

    append_calls, appended_content = asyncio.run(run_job())

    expected_draft = "".join(f"片段{i:03d}" for i in range(MANY_DELTAS))
    assert appended_content == expected_draft, "total appended content must equal concatenated deltas"
    assert append_calls < MANY_DELTAS, (
        f"append_report_delta was called {append_calls} times for {MANY_DELTAS} deltas — "
        "must be batched, not per-delta"
    )


def test_report_delta_events_have_no_draft_report_in_payload(monkeypatch) -> None:
    """Live report_delta SSE events must not carry draft_report — frontend accumulates via delta."""

    class SingleDeltaRuntime:
        async def run(self, job_id: str, request: ResearchRequest):
            yield ResearchEvent(
                job_id=job_id,
                type="report_delta",
                message="报告流式输出",
                payload={"delta": "片段"},
            )
            yield ResearchEvent(
                job_id=job_id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )

    published: list[ResearchEvent] = []

    async def fake_publish(job_id: str, event: ResearchEvent) -> None:
        published.append(event)

    async def run_job():
        store = InMemoryJobStore()
        request = ResearchRequest(query="测试 delta payload", mode="quick", provider="mock")
        job = await store.create_job(
            request,
            provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        monkeypatch.setattr(routes, "job_store", store)
        monkeypatch.setattr(routes, "runtime", SingleDeltaRuntime())
        monkeypatch.setattr(routes, "publish_live_event", fake_publish)
        await routes.run_research_job(job.id, request)

    asyncio.run(run_job())

    delta_events = [e for e in published if e.type == "report_delta"]
    assert delta_events, "expected at least one report_delta event"
    for event in delta_events:
        assert "draft_report" not in event.payload, (
            "report_delta payload must not contain draft_report — "
            "attaching it requires an extra DB round-trip per token"
        )


def test_sse_loop_does_not_call_get_job_per_live_event(monkeypatch) -> None:
    """SSE while-loop must NOT call get_job for every queued event.

    With Neon RTT at ~325ms each call, one get_job per event adds ~325ms of
    latency to every streaming token. The loop should only consult the DB when
    the queue times out (no events for 0.5 s), not on every normal dequeue.
    """
    LIVE_EVENTS = 10

    async def run():
        store = InMemoryJobStore()
        request = ResearchRequest(query="SSE 不频繁查数据库", mode="quick", provider="mock")
        job = await store.create_job(
            request, provider="mock",
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
        )
        await store.start_job(job.id)

        # Pre-populate the live queue so every queue.get() is instant (no timeouts).
        live_q: asyncio.Queue[ResearchEvent] = asyncio.Queue()
        for i in range(LIVE_EVENTS):
            live_q.put_nowait(ResearchEvent(
                job_id=job.id, type="report_delta", message="", payload={"delta": f"片段{i}"},
            ))
        live_q.put_nowait(ResearchEvent(
            job_id=job.id, type="completed", message="完成",
            payload={"final_report": "报告", "sources": []},
        ))

        # Count every get_job call against this store.
        db_calls: list[str] = []
        orig_get_job = store.get_job

        async def tracking_get_job(job_id, **kw):
            db_calls.append(job_id)
            return await orig_get_job(job_id, **kw)

        store.get_job = tracking_get_job
        monkeypatch.setattr(routes, "job_store", store)

        async def mock_register(jid):
            return live_q

        async def mock_unregister(jid, q):
            pass

        monkeypatch.setattr(routes, "register_live_event_queue", mock_register)
        monkeypatch.setattr(routes, "unregister_live_event_queue", mock_unregister)

        identity = RequestIdentity(
            anonymous_id=VISITOR_HEADERS["X-PZ-Visitor-ID"],
            user_id=None,
        )

        # One get_job for the auth check in stream_research_events itself.
        response = await routes.stream_research_events(
            job_id=job.id, after=None, last_event_id=None, identity=identity,
        )
        auth_calls = len(db_calls)  # should be 1

        # Drain the SSE generator — this is where the while-loop runs.
        async for _ in response.body_iterator:
            pass

        return db_calls, auth_calls, LIVE_EVENTS

    db_calls, auth_calls, n = asyncio.run(run())

    # Inside event_stream():
    #   1 call for snapshot (always)
    #   N+1 calls in the while-loop (current broken code: once per event)
    #   0 calls in the while-loop (fixed code: only on TimeoutError)
    # With all events pre-loaded, queue.get() never times out → 0 while-loop calls expected.
    inside_generator_calls = len(db_calls) - auth_calls
    assert inside_generator_calls <= 2, (
        f"expected ≤2 get_job calls inside event_stream (snapshot + at most 1 timeout check) "
        f"for {n} live events; got {inside_generator_calls}. "
        "The SSE while-loop must not call get_job on every dequeue."
    )
