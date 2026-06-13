from __future__ import annotations

import asyncio
import json
import logging
import traceback
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchCredentials, ResearchEvent, ResearchJob, ResearchRequest
from app.agent.tools import build_default_tool_registry
from app.auth import AuthenticationError, ClerkAuthenticator, RequestIdentity
from app.config import (
    get_settings,
    missing_provider_requirements,
    missing_search_requirements,
    provider_model,
    resolve_model_route,
)
from app.error_handling import classify_failure, redact_sensitive, sanitize_failed_event
from app.reporting import PdfExportError, PdfExporter, pdf_export_filename
from app.storage import SqlJobStore, upgrade_database


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
settings = get_settings()
authenticator = ClerkAuthenticator(
    jwt_key=settings.clerk_jwt_key,
    authorized_parties=settings.clerk_authorized_parties,
    clock_skew_seconds=settings.clerk_clock_skew_seconds,
)
job_store = SqlJobStore(
    settings.database_url,
    auto_create_schema=False,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout_seconds=settings.database_pool_timeout_seconds,
    pool_recycle_seconds=settings.database_pool_recycle_seconds,
)
runtime = AgentRuntime(
    provider_factory=ProviderFactory(settings),
    tool_registry=build_default_tool_registry(settings),
    tool_registry_factory=lambda request: build_default_tool_registry(
        settings,
        search_api_key_override=request.search_api_key,
        reader_api_key_override=request.reader_api_key,
    ),
    max_llm_retries=settings.llm_max_retries,
    llm_retry_base_delay_seconds=settings.llm_retry_base_delay_seconds,
    llm_timeout_seconds=settings.llm_timeout_seconds,
    evidence_extraction_model=settings.evidence_extraction_model,
    evidence_extraction_models={
        "openai": settings.evidence_extraction_model,
        "anthropic": settings.anthropic_evidence_model,
        "gemini": settings.gemini_evidence_model,
    },
    evidence_extraction_concurrency=settings.visit_max_concurrency,
)
pdf_exporter = PdfExporter(
    timeout_seconds=settings.pdf_export_timeout_seconds,
    max_concurrency=settings.pdf_export_max_concurrency,
    chromium_executable_path=settings.pdf_chromium_executable_path,
)
live_event_queues: dict[str, set[asyncio.Queue[ResearchEvent]]] = {}
live_event_lock = asyncio.Lock()
running_tasks: dict[str, asyncio.Task[None]] = {}
running_tasks_lock = asyncio.Lock()


async def register_live_event_queue(job_id: str) -> asyncio.Queue[ResearchEvent]:
    queue: asyncio.Queue[ResearchEvent] = asyncio.Queue()
    async with live_event_lock:
        live_event_queues.setdefault(job_id, set()).add(queue)
    return queue


async def unregister_live_event_queue(job_id: str, queue: asyncio.Queue[ResearchEvent]) -> None:
    async with live_event_lock:
        queues = live_event_queues.get(job_id)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            live_event_queues.pop(job_id, None)


async def publish_live_event(job_id: str, event: ResearchEvent) -> None:
    async with live_event_lock:
        queues = list(live_event_queues.get(job_id, set()))
    for queue in queues:
        await queue.put(event)


async def register_running_task(job_id: str, task: asyncio.Task[None]) -> None:
    async with running_tasks_lock:
        running_tasks[job_id] = task


async def unregister_running_task(job_id: str, task: asyncio.Task[None]) -> None:
    async with running_tasks_lock:
        if running_tasks.get(job_id) is task:
            running_tasks.pop(job_id, None)


async def get_running_task(job_id: str) -> asyncio.Task[None] | None:
    async with running_tasks_lock:
        return running_tasks.get(job_id)


def events_after(events: list[ResearchEvent], cursor: str | None) -> list[ResearchEvent]:
    if not cursor:
        return events
    for index, event in enumerate(events):
        if event.id == cursor:
            return events[index + 1 :]
    return events


def format_sse(event: ResearchEvent, *, include_id: bool = True) -> str:
    payload = event.model_dump(mode="json")
    prefix = f"id: {event.id}\n" if include_id else ""
    return f"{prefix}data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def get_request_identity(
    authorization: str | None = Header(default=None, alias="Authorization"),
    visitor_header: str | None = Header(default=None, alias="X-PZ-Visitor-ID"),
    visitor_query: str | None = Query(default=None, alias="visitor_id"),
) -> RequestIdentity:
    try:
        identity = authenticator.authenticate(
            authorization=authorization,
            visitor_id=visitor_header or visitor_query,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if identity.user_id and identity.anonymous_id:
        await job_store.claim_anonymous_jobs(
            identity.anonymous_id,
            user_id=identity.user_id,
        )
    return identity


@router.post("/research-jobs", response_model=ResearchJob)
async def create_research_job(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    identity: RequestIdentity = Depends(get_request_identity),
) -> ResearchJob:
    route = resolve_model_route(
        settings,
        requested_provider=request.provider,
        requested_model=request.model,
    )
    # BYOK is community-only; cloud edition ignores client-supplied credentials.
    byok_api_key = request.api_key if settings.edition == "community" else None
    byok_base_url = request.base_url if settings.edition == "community" else None
    byok_search_api_key = (
        request.search_api_key if settings.edition == "community" else None
    )
    byok_reader_api_key = (
        request.reader_api_key if settings.edition == "community" else None
    )
    routed_request = request.model_copy(
        update={
            "provider": route.provider,
            "model": route.model,
            "api_key": byok_api_key,
            "base_url": byok_base_url,
            "search_api_key": byok_search_api_key,
            "reader_api_key": byok_reader_api_key,
        }
    )
    missing = missing_provider_requirements(
        settings,
        route.provider,
        model_override=route.model,
        api_key_override=byok_api_key,
        search_api_key_override=byok_search_api_key,
    )
    if missing:
        logger.warning(
            "research_creation_configuration_missing provider=%s model=%s missing=%s",
            route.provider,
            route.model,
            missing,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "研究服务暂时不可用，请稍后重试。",
                "code": "service_unavailable",
                "retryable": False,
            },
        )
    job = await job_store.create_job(
        routed_request,
        provider=route.provider,
        anonymous_id=identity.anonymous_id,
        user_id=identity.user_id,
        routing_version=route.routing_version,
    )
    background_tasks.add_task(run_research_job, job.id, routed_request)
    return job


@router.get("/readiness")
async def get_readiness() -> dict[str, object]:
    providers = {}
    for provider in ["mock", "openai", "anthropic", "gemini"]:
        missing = missing_provider_requirements(settings, provider)
        providers[provider] = {
            "ready": not missing,
            "missing": missing,
            "model": provider_model(settings, provider) or None,
        }
    search_missing = missing_search_requirements(settings)
    try:
        database_ready = await job_store.check_connection()
    except Exception as exc:
        logger.error(
            "database_readiness_check_failed error=%s",
            redact_sensitive(exc),
        )
        database_ready = False
    return {
        "edition": settings.edition,
        "providers": providers,
        "tools": {
            "search": {
                "ready": not search_missing,
                "missing": search_missing,
                "provider": settings.search_provider,
                "engine": settings.academic_search_engine,
            },
            "visit": {
                "ready": True,
                "missing": [],
                "optional_missing": [] if settings.jina_api_key else ["JINA_API_KEY"],
            },
        },
        "database": {
            "ready": database_ready,
            "backend": job_store.backend_name,
        },
        "auth": {
            "ready": authenticator.enabled,
            "provider": "clerk",
        },
    }


@router.get("/models")
async def get_model_options() -> dict[str, object]:
    route = resolve_model_route(settings)
    return {
        "selection_enabled": route.selection_enabled,
        "routing_version": route.routing_version,
        "providers": {
            "mock": [
                {"id": "", "label": "开发模式"},
            ],
            "openai": [
                {"id": model, "label": model}
                for model in settings.openai_model_options
            ],
            "anthropic": [
                {"id": model, "label": model}
                for model in settings.anthropic_model_options
            ],
            "gemini": [
                {"id": model, "label": model}
                for model in settings.gemini_model_options
            ],
        },
        "defaults": {
            "provider": route.provider,
            "openai": provider_model(settings, "openai") or None,
            "anthropic": provider_model(settings, "anthropic") or None,
            "gemini": provider_model(settings, "gemini") or None,
        },
    }


@router.get("/models/openai")
async def get_openai_available_models() -> dict[str, object]:
    missing = missing_provider_requirements(settings, "openai", require_real_search=False)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "OpenAI 配置不完整，请先补齐环境变量",
                "missing": missing,
            },
        )

    from openai import AsyncOpenAI

    client_kwargs = {
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_base_url or "https://api.openai.com/v1",
    }

    try:
        response = await AsyncOpenAI(**client_kwargs).models.list()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "无法从 OpenAI 获取模型列表",
                "error": str(exc),
            },
        ) from exc

    configured = list(settings.openai_model_options)
    available = sorted(
        model.id
        for model in response.data
        if getattr(model, "id", "")
    )
    available_set = set(available)
    return {
        "configured": configured,
        "available": available,
        "configured_available": [model for model in configured if model in available_set],
    }


@router.get("/models/anthropic")
async def get_anthropic_available_models() -> dict[str, object]:
    missing = missing_provider_requirements(settings, "anthropic", require_real_search=False)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Claude 配置不完整，请先补齐环境变量",
                "missing": missing,
            },
        )

    from anthropic import AsyncAnthropic

    try:
        async with AsyncAnthropic(api_key=settings.anthropic_api_key) as client:
            response = await client.models.list(limit=100)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "无法从 Anthropic 获取模型列表",
                "error": str(exc),
            },
        ) from exc

    configured = list(settings.anthropic_model_options)
    available = sorted(
        model.id
        for model in response.data
        if getattr(model, "id", "")
    )
    available_set = set(available)
    return {
        "configured": configured,
        "available": available,
        "configured_available": [model for model in configured if model in available_set],
    }


@router.get("/models/gemini")
async def get_gemini_available_models() -> dict[str, object]:
    missing = missing_provider_requirements(settings, "gemini", require_real_search=False)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Gemini 配置不完整，请先补齐环境变量",
                "missing": missing,
            },
        )

    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        pager = await client.aio.models.list(config={"page_size": 100})
        available = sorted([
            model.name.removeprefix("models/")
            async for model in pager
            if getattr(model, "name", "")
            and "generateContent" in (getattr(model, "supported_actions", None) or [])
        ])
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "无法从 Gemini 获取模型列表",
                "error": str(exc),
            },
        ) from exc
    finally:
        await client.aio.aclose()

    configured = list(settings.gemini_model_options)
    available_set = set(available)
    return {
        "configured": configured,
        "available": available,
        "configured_available": [model for model in configured if model in available_set],
    }


@router.get("/research-jobs/{job_id}", response_model=ResearchJob)
async def get_research_job(
    job_id: str,
    identity: RequestIdentity = Depends(get_request_identity),
) -> ResearchJob:
    job = await job_store.get_job(
        job_id,
        **identity.owner_kwargs,
    )
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    return job


@router.get("/research-jobs", response_model=list[ResearchJob])
async def list_research_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: RequestIdentity = Depends(get_request_identity),
) -> list[ResearchJob]:
    return await job_store.list_jobs(
        **identity.owner_kwargs,
        limit=limit,
        offset=offset,
    )


@router.get("/research-jobs/{job_id}/export/pdf")
async def export_research_job_pdf(
    job_id: str,
    identity: RequestIdentity = Depends(get_request_identity),
) -> Response:
    job = await job_store.get_job(job_id, **identity.owner_kwargs)
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")

    report = job.final_report or job.draft_report
    if not report:
        raise HTTPException(status_code=409, detail="报告尚未生成，无法导出 PDF")

    try:
        pdf = await pdf_exporter.render(job, report)
    except PdfExportError as exc:
        raise HTTPException(status_code=503, detail="PDF 生成失败，请稍后重试") from exc

    filename = pdf_export_filename(job.query, job.id)
    fallback_filename = f"pz-deep-research-{job.id[:8]}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": (
                f'attachment; filename="{fallback_filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.post("/research-jobs/{job_id}/rerun", response_model=ResearchJob)
async def rerun_research_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    credentials: ResearchCredentials | None = None,
    identity: RequestIdentity = Depends(get_request_identity),
) -> ResearchJob:
    source_job = await job_store.get_job(job_id, **identity.owner_kwargs)
    if not source_job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    if source_job.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="任务仍在运行，无法重新运行")

    credentials = credentials or ResearchCredentials()
    byok_api_key = credentials.api_key if settings.edition == "community" else None
    byok_base_url = credentials.base_url if settings.edition == "community" else None
    byok_search_api_key = (
        credentials.search_api_key if settings.edition == "community" else None
    )
    byok_reader_api_key = (
        credentials.reader_api_key if settings.edition == "community" else None
    )
    missing = missing_provider_requirements(
        settings,
        source_job.provider,
        model_override=source_job.model,
        api_key_override=byok_api_key,
        search_api_key_override=byok_search_api_key,
    )
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "原任务使用的研究配置当前不可用，请先补齐环境变量",
                "provider": source_job.provider,
                "missing": missing,
            },
        )

    request = ResearchRequest(
        query=source_job.query,
        mode=source_job.mode,
        provider=source_job.provider,
        model=source_job.model,
        api_key=byok_api_key,
        base_url=byok_base_url,
        search_api_key=byok_search_api_key,
        reader_api_key=byok_reader_api_key,
    )
    rerun_job = await job_store.create_job(
        request,
        provider=source_job.provider,
        anonymous_id=identity.anonymous_id,
        user_id=identity.user_id,
        rerun_of_job_id=source_job.id,
        routing_version=source_job.routing_version or "legacy",
    )
    background_tasks.add_task(run_research_job, rerun_job.id, request)
    return rerun_job


@router.post("/research-jobs/{job_id}/retry", response_model=ResearchJob)
async def retry_failed_research_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    credentials: ResearchCredentials | None = None,
    identity: RequestIdentity = Depends(get_request_identity),
) -> ResearchJob:
    source_job = await job_store.get_job(job_id, **identity.owner_kwargs)
    if not source_job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    if source_job.status != "failed":
        raise HTTPException(status_code=409, detail="只有失败任务可以重试")
    if not source_job.error_retryable:
        raise HTTPException(status_code=409, detail="当前失败不可直接重试，请重新发起研究")

    credentials = credentials or ResearchCredentials()
    byok_api_key = credentials.api_key if settings.edition == "community" else None
    byok_base_url = credentials.base_url if settings.edition == "community" else None
    byok_search_api_key = (
        credentials.search_api_key if settings.edition == "community" else None
    )
    byok_reader_api_key = (
        credentials.reader_api_key if settings.edition == "community" else None
    )
    missing = missing_provider_requirements(
        settings,
        source_job.provider,
        model_override=source_job.model,
        api_key_override=byok_api_key,
        search_api_key_override=byok_search_api_key,
    )
    if missing:
        logger.warning(
            "research_retry_configuration_missing job_id=%s provider=%s missing=%s",
            source_job.id,
            source_job.provider,
            missing,
        )
        raise HTTPException(status_code=503, detail="研究服务暂时不可用，请稍后重试")

    request = ResearchRequest(
        query=source_job.query,
        mode=source_job.mode,
        provider=source_job.provider,
        model=source_job.model,
        api_key=byok_api_key,
        base_url=byok_base_url,
        search_api_key=byok_search_api_key,
        reader_api_key=byok_reader_api_key,
    )
    retry_context = None
    if source_job.error_stage == "report":
        retry_context = await job_store.get_retry_context(source_job.id)

    retry_job = await job_store.create_job(
        request,
        provider=source_job.provider,
        anonymous_id=identity.anonymous_id,
        user_id=identity.user_id,
        rerun_of_job_id=source_job.id,
        routing_version=source_job.routing_version or "legacy",
    )
    background_tasks.add_task(
        run_research_job,
        retry_job.id,
        request,
        retry_context,
    )
    return retry_job


@router.post("/research-jobs/{job_id}/cancel", response_model=ResearchJob)
async def cancel_research_job(
    job_id: str,
    identity: RequestIdentity = Depends(get_request_identity),
) -> ResearchJob:
    job, changed = await job_store.request_cancel(
        job_id,
        **identity.owner_kwargs,
    )
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    if not changed:
        if job.status == "cancelled":
            return job
        raise HTTPException(status_code=409, detail="任务已经结束，无法取消")

    cancelled_event = ResearchEvent(
        job_id=job_id,
        type="cancelled",
        message="研究任务已取消",
        payload={"reason": "user_requested"},
    )
    await job_store.add_event(cancelled_event)
    await publish_live_event(job_id, cancelled_event)

    task = await get_running_task(job_id)
    current_task = asyncio.current_task()
    if task and task is not current_task and not task.done():
        task.cancel()

    updated_job = await job_store.get_job(job_id)
    return updated_job or job


@router.get("/research-jobs/{job_id}/events", response_model=list[ResearchEvent])
async def get_research_events(
    job_id: str,
    identity: RequestIdentity = Depends(get_request_identity),
) -> list[ResearchEvent]:
    job = await job_store.get_job(
        job_id,
        **identity.owner_kwargs,
    )
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    return await job_store.list_events(job_id)


@router.get("/research-jobs/{job_id}/stream")
async def stream_research_events(
    job_id: str,
    after: str | None = None,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    identity: RequestIdentity = Depends(get_request_identity),
) -> StreamingResponse:
    job = await job_store.get_job(job_id, **identity.owner_kwargs)
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")

    async def event_stream():
        queue = await register_live_event_queue(job_id)
        sent_event_ids: set[str] = set()
        try:
            current_job = await job_store.get_job(job_id)
            if current_job:
                snapshot_event = ResearchEvent(
                    job_id=job_id,
                    type="job_snapshot",
                    message="已恢复任务状态",
                    payload={
                        "status": current_job.status,
                        "draft_report": current_job.draft_report,
                        "final_report": current_job.final_report,
                        "error": current_job.error,
                        "error_code": current_job.error_code,
                        "error_retryable": current_job.error_retryable,
                        "error_stage": current_job.error_stage,
                    },
                )
                yield format_sse(snapshot_event, include_id=False)

            events = events_after(
                await job_store.list_events(job_id),
                last_event_id or after,
            )
            for event in events:
                sent_event_ids.add(event.id)
                yield format_sse(event)

            while True:
                current_job = await job_store.get_job(job_id)
                if current_job and current_job.status in {"completed", "failed", "cancelled"} and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if event.id in sent_event_ids:
                    continue
                sent_event_ids.add(event.id)
                yield format_sse(
                    event,
                    include_id=event.type not in {"llm_delta", "report_delta"},
                )
                if event.type in {"completed", "failed", "cancelled"}:
                    break
        finally:
            await unregister_live_event_queue(job_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def initialize_job_store() -> int:
    await upgrade_database(settings.database_migration_url)
    await job_store.initialize()
    return await job_store.recover_incomplete_jobs()


async def dispose_job_store() -> None:
    await job_store.dispose()


async def run_research_job(
    job_id: str,
    request: ResearchRequest,
    retry_context: dict[str, object] | None = None,
) -> None:
    task = asyncio.current_task()
    if task:
        await register_running_task(job_id, task)
    try:
        if not await job_store.start_job(job_id):
            return
        event_stream = (
            runtime.resume_report(job_id, request, retry_context)
            if retry_context
            else runtime.run(job_id, request)
        )
        async for event in event_stream:
            current_job = await job_store.get_job(job_id)
            if not current_job or current_job.status == "cancelled":
                return
            if event.type == "report_checkpoint":
                await job_store.save_retry_context(job_id, event.payload)
                continue
            if event.type == "failed":
                logger.error(
                    "research_job_failed job_id=%s provider=%s model=%s event=%s",
                    job_id,
                    request.provider,
                    request.model,
                    redact_sensitive(
                        {
                            "message": event.message,
                            "payload": event.payload,
                        }
                    ),
                )
                event, _ = sanitize_failed_event(event)
            if event.type == "report_delta":
                delta = event.payload.get("delta")
                if isinstance(delta, str):
                    await job_store.append_report_delta(job_id, delta)
                    draft_job = await job_store.get_job(job_id)
                    if draft_job:
                        event.payload["draft_report"] = draft_job.draft_report
            elif event.type != "llm_delta":
                await job_store.add_event(event)
            await publish_live_event(job_id, event)
    except asyncio.CancelledError:
        current_job = await job_store.get_job(job_id)
        if current_job and current_job.status not in {"completed", "failed", "cancelled"}:
            _, changed = await job_store.request_cancel(job_id)
            if changed:
                cancelled_event = ResearchEvent(
                    job_id=job_id,
                    type="cancelled",
                    message="研究任务已取消",
                    payload={"reason": "task_cancelled"},
                )
                await job_store.add_event(cancelled_event)
                await publish_live_event(job_id, cancelled_event)
        return
    except Exception as exc:
        logger.error(
            "research_job_unhandled_error job_id=%s provider=%s model=%s error=%s traceback=%s",
            job_id,
            request.provider,
            request.model,
            redact_sensitive(exc),
            "".join(traceback.format_tb(exc.__traceback__)),
        )
        classified = classify_failure(error=exc)
        failed_event = ResearchEvent(
            job_id=job_id,
            type="failed",
            message=classified.message,
            payload={
                "error_code": classified.code,
                "retryable": classified.retryable,
                "stage": classified.stage,
            },
        )
        await job_store.add_event(failed_event)
        await publish_live_event(job_id, failed_event)
    finally:
        if task:
            await unregister_running_task(job_id, task)
