from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Optional

from app.agent.schemas import ResearchEvent, ResearchJob, ResearchRequest, utc_now


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJob] = {}
        self._events: dict[str, list[ResearchEvent]] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, request: ResearchRequest, provider: str) -> ResearchJob:
        job = ResearchJob(
            query=request.query,
            mode=request.mode,
            provider=provider,
            model=request.model,
        )
        async with self._lock:
            self._jobs[job.id] = job
            self._events[job.id] = []
        return job

    async def get_job(self, job_id: str) -> Optional[ResearchJob]:
        async with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    async def list_events(self, job_id: str) -> list[ResearchEvent]:
        async with self._lock:
            return list(self._events.get(job_id, []))

    async def add_event(self, event: ResearchEvent) -> None:
        async with self._lock:
            self._events.setdefault(event.job_id, []).append(event)
            job = self._jobs.get(event.job_id)
            if not job:
                return
            job.updated_at = utc_now().astimezone(timezone.utc)
            if event.type == "completed":
                job.status = "completed"
                job.final_report = event.payload.get("final_report")
                job.draft_report = job.final_report or job.draft_report
            elif event.type == "failed":
                job.status = "failed"
                job.error = event.message
            elif event.type == "cancelled":
                job.status = "cancelled"
            elif event.type == "report_reset":
                job.draft_report = ""

    async def start_job(self, job_id: str) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "queued":
                return False
            job.status = "running"
            job.updated_at = utc_now().astimezone(timezone.utc)
            return True

    async def request_cancel(self, job_id: str) -> tuple[Optional[ResearchJob], bool]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None, False
            if job.status not in {"queued", "running"}:
                return job.model_copy(deep=True), False
            job.status = "cancelled"
            job.updated_at = utc_now().astimezone(timezone.utc)
            return job.model_copy(deep=True), True

    async def append_report_delta(self, job_id: str, delta: str) -> None:
        if not delta:
            return
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in {"completed", "failed", "cancelled"}:
                return
            job.draft_report += delta
            job.updated_at = utc_now().astimezone(timezone.utc)

    async def update_status(self, job_id: str, status: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = utc_now().astimezone(timezone.utc)
