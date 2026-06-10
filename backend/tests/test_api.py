from __future__ import annotations

import asyncio

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
VISITOR_HEADERS = {"X-PZ-Visitor-ID": "11111111-1111-4111-8111-111111111111"}
OTHER_VISITOR_HEADERS = {"X-PZ-Visitor-ID": "22222222-2222-4222-8222-222222222222"}


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


def test_model_options_endpoint_returns_provider_candidates() -> None:
    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    openai_models = [item["id"] for item in payload["providers"]["openai"]]
    anthropic_models = [item["id"] for item in payload["providers"]["anthropic"]]
    gemini_models = [item["id"] for item in payload["providers"]["gemini"]]
    assert "gpt-5.5" in openai_models
    assert "gpt-5.4-mini" in openai_models
    assert "claude-opus-4-8" in anthropic_models
    assert "claude-sonnet-4-6" in anthropic_models
    assert "gemini-3.5-flash" in gemini_models
    assert "gemini-3.1-pro-preview" in gemini_models


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
    mock_settings = Settings(default_provider="mock", search_provider="mock")
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
            VISITOR_HEADERS["X-PZ-Visitor-ID"],
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
