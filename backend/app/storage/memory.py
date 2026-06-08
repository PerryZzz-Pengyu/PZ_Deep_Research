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
            return self._jobs.get(job_id)

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
            elif event.type == "failed":
                job.status = "failed"
                job.error = event.message

    async def update_status(self, job_id: str, status: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = utc_now().astimezone(timezone.utc)
