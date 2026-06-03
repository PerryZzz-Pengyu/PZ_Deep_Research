from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.providers import ProviderFactory
from app.agent.runtime import AgentRuntime
from app.agent.schemas import ResearchEvent, ResearchJob, ResearchRequest
from app.agent.tools import build_default_tool_registry
from app.config import missing_provider_requirements, missing_search_requirements, provider_model, get_settings
from app.storage import InMemoryJobStore


router = APIRouter(prefix="/api")
settings = get_settings()
job_store = InMemoryJobStore()
runtime = AgentRuntime(
    provider_factory=ProviderFactory(settings),
    tool_registry=build_default_tool_registry(settings),
    max_llm_retries=settings.llm_max_retries,
    llm_timeout_seconds=settings.llm_timeout_seconds,
)


@router.post("/research-jobs", response_model=ResearchJob)
async def create_research_job(request: ResearchRequest, background_tasks: BackgroundTasks) -> ResearchJob:
    provider = request.provider or settings.default_provider
    missing = missing_provider_requirements(settings, provider, model_override=request.model)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "真实研究配置不完整，请先补齐环境变量",
                "provider": provider,
                "missing": missing,
            },
        )
    job = await job_store.create_job(request, provider=provider)
    background_tasks.add_task(run_research_job, job.id, request)
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
    return {
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
    }


@router.get("/models")
async def get_model_options() -> dict[str, object]:
    return {
        "providers": {
            "mock": [
                {"id": "", "label": "开发模式"},
            ],
            "openai": [
                {"id": model, "label": model}
                for model in settings.openai_model_options
            ],
            "anthropic": [
                {"id": settings.anthropic_model, "label": settings.anthropic_model},
            ],
            "gemini": [
                {"id": settings.gemini_model, "label": settings.gemini_model},
            ],
        },
        "defaults": {
            "provider": settings.default_provider,
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


@router.get("/research-jobs/{job_id}", response_model=ResearchJob)
async def get_research_job(job_id: str) -> ResearchJob:
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    return job


@router.get("/research-jobs/{job_id}/events", response_model=list[ResearchEvent])
async def get_research_events(job_id: str) -> list[ResearchEvent]:
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    return await job_store.list_events(job_id)


@router.get("/research-jobs/{job_id}/stream")
async def stream_research_events(job_id: str) -> StreamingResponse:
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="研究任务不存在")

    async def event_stream():
        sent_count = 0
        while True:
            events = await job_store.list_events(job_id)
            for event in events[sent_count:]:
                payload = event.model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            sent_count = len(events)
            current_job = await job_store.get_job(job_id)
            if current_job and current_job.status in {"completed", "failed", "cancelled"} and sent_count == len(events):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def run_research_job(job_id: str, request: ResearchRequest) -> None:
    await job_store.update_status(job_id, "running")
    try:
        async for event in runtime.run(job_id, request):
            await job_store.add_event(event)
    except Exception as exc:
        await job_store.add_event(
            ResearchEvent(
                job_id=job_id,
                type="failed",
                message=f"研究任务失败：{exc}",
                payload={"error": str(exc)},
            )
        )
