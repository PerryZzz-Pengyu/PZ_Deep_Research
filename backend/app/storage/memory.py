from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Optional

from app.agent.schemas import ResearchEvent, ResearchJob, ResearchRequest, utc_now


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJob] = {}
        self._events: dict[str, list[ResearchEvent]] = {}
        self._owners: dict[str, tuple[Optional[str], Optional[str]]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        return None

    async def dispose(self) -> None:
        return None

    async def create_job(
        self,
        request: ResearchRequest,
        provider: str,
        *,
        anonymous_id: str = "local-development",
        user_id: Optional[str] = None,
    ) -> ResearchJob:
        job = ResearchJob(
            query=request.query,
            mode=request.mode,
            provider=provider,
            model=request.model,
        )
        async with self._lock:
            self._jobs[job.id] = job
            self._events[job.id] = []
            self._owners[job.id] = (anonymous_id if not user_id else None, user_id)
        return job

    def _owner_matches(
        self,
        job_id: str,
        *,
        anonymous_id: Optional[str],
        user_id: Optional[str],
    ) -> bool:
        if anonymous_id is None and user_id is None:
            return True
        stored_anonymous_id, stored_user_id = self._owners.get(job_id, (None, None))
        if user_id is not None:
            return stored_user_id == user_id
        return stored_anonymous_id == anonymous_id

    async def get_job(
        self,
        job_id: str,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[ResearchJob]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and not self._owner_matches(
                job_id,
                anonymous_id=anonymous_id,
                user_id=user_id,
            ):
                return None
            return job.model_copy(deep=True) if job else None

    async def list_jobs(
        self,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchJob]:
        async with self._lock:
            jobs = [
                job.model_copy(deep=True)
                for job_id, job in self._jobs.items()
                if self._owner_matches(
                    job_id,
                    anonymous_id=anonymous_id,
                    user_id=user_id,
                )
            ]
        jobs.sort(key=lambda item: item.updated_at, reverse=True)
        return jobs[offset : offset + limit]

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

    async def request_cancel(
        self,
        job_id: str,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[Optional[ResearchJob], bool]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None, False
            if not self._owner_matches(
                job_id,
                anonymous_id=anonymous_id,
                user_id=user_id,
            ):
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

    async def recover_incomplete_jobs(self) -> int:
        async with self._lock:
            incomplete_ids = [
                job_id
                for job_id, job in self._jobs.items()
                if job.status in {"queued", "running"}
            ]
            for job_id in incomplete_ids:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error = "服务重启，未完成的研究任务已中断"
                job.updated_at = utc_now().astimezone(timezone.utc)
                self._events[job_id].append(
                    ResearchEvent(
                        job_id=job_id,
                        type="failed",
                        message="服务重启，未完成的研究任务已中断",
                        payload={"reason": "service_restarted"},
                    )
                )
            return len(incomplete_ids)

    async def claim_anonymous_jobs(self, anonymous_id: str, *, user_id: str) -> int:
        async with self._lock:
            claimed = 0
            for job_id, owner in list(self._owners.items()):
                stored_anonymous_id, stored_user_id = owner
                if stored_anonymous_id == anonymous_id and stored_user_id is None:
                    self._owners[job_id] = (None, user_id)
                    claimed += 1
            return claimed
