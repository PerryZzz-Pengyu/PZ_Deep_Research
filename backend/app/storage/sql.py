from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    and_,
    insert,
    select,
    update,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.agent.schemas import ResearchEvent, ResearchJob, ResearchRequest, utc_now


metadata = MetaData()

jobs = Table(
    "research_jobs",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("rerun_of_job_id", String(32), nullable=True),
    Column("routing_version", String(64), nullable=True),
    Column("query", Text, nullable=False),
    Column("mode", String(16), nullable=False),
    Column("provider", String(32), nullable=False),
    Column("model", String(160), nullable=True),
    Column("status", String(16), nullable=False),
    Column("draft_report", Text, nullable=False, default=""),
    Column("final_report", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("error_retryable", Boolean, nullable=False, default=False),
    Column("error_stage", String(32), nullable=True),
    Column("retry_context", JSON, nullable=True),
    Column("anonymous_id", String(128), nullable=True),
    Column("user_id", String(128), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

events = Table(
    "research_events",
    metadata,
    Column("id", String(32), primary_key=True),
    Column(
        "job_id",
        String(32),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("type", String(64), nullable=False),
    Column("message", Text, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Index("ix_research_jobs_anonymous_updated", jobs.c.anonymous_id, jobs.c.updated_at)
Index("ix_research_jobs_user_updated", jobs.c.user_id, jobs.c.updated_at)
Index("ix_research_jobs_rerun_of", jobs.c.rerun_of_job_id)
Index("ix_research_events_job_created", events.c.job_id, events.c.created_at)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _job_from_row(row) -> ResearchJob:
    return ResearchJob(
        id=row.id,
        rerun_of_job_id=row.rerun_of_job_id,
        routing_version=row.routing_version,
        query=row.query,
        mode=row.mode,
        provider=row.provider,
        model=row.model,
        status=row.status,
        draft_report=row.draft_report or "",
        final_report=row.final_report,
        error=row.error,
        error_code=row.error_code,
        error_retryable=bool(row.error_retryable),
        error_stage=row.error_stage,
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
    )


def _event_from_row(row) -> ResearchEvent:
    return ResearchEvent(
        id=row.id,
        job_id=row.job_id,
        type=row.type,
        message=row.message,
        payload=row.payload or {},
        created_at=_as_utc(row.created_at),
    )


class SqlJobStore:
    def __init__(
        self,
        database_url: str,
        *,
        auto_create_schema: bool = True,
        pool_size: int = 5,
        max_overflow: int = 5,
        pool_timeout_seconds: int = 30,
        pool_recycle_seconds: int = 300,
    ) -> None:
        self.database_url = database_url
        self.auto_create_schema = auto_create_schema
        engine_options: dict[str, object] = {}
        if not database_url.startswith("sqlite"):
            engine_options.update(
                pool_pre_ping=True,
                pool_size=max(1, pool_size),
                max_overflow=max(0, max_overflow),
                pool_timeout=max(1, pool_timeout_seconds),
                pool_recycle=max(30, pool_recycle_seconds),
            )
        self.engine: AsyncEngine = create_async_engine(database_url, **engine_options)
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            if self.database_url.startswith("sqlite"):
                database_path = self.database_url.split("///", 1)[-1]
                if database_path and database_path != ":memory:":
                    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            if self.auto_create_schema:
                async with self.engine.begin() as connection:
                    await connection.run_sync(metadata.create_all)
            self._initialized = True

    async def dispose(self) -> None:
        await self.engine.dispose()
        self._initialized = False

    async def check_connection(self) -> bool:
        await self._ready()
        async with self.engine.connect() as connection:
            return (await connection.scalar(text("SELECT 1"))) == 1

    @property
    def backend_name(self) -> str:
        return self.engine.url.get_backend_name()

    async def _ready(self) -> None:
        if not self._initialized:
            await self.initialize()

    @staticmethod
    def _owner_clause(
        *,
        anonymous_id: Optional[str],
        user_id: Optional[str],
    ):
        if user_id is not None:
            return jobs.c.user_id == user_id
        if anonymous_id is not None:
            return jobs.c.anonymous_id == anonymous_id
        return None

    async def create_job(
        self,
        request: ResearchRequest,
        provider: str,
        *,
        anonymous_id: str = "local-development",
        user_id: Optional[str] = None,
        rerun_of_job_id: Optional[str] = None,
        routing_version: Optional[str] = None,
    ) -> ResearchJob:
        await self._ready()
        job = ResearchJob(
            rerun_of_job_id=rerun_of_job_id,
            routing_version=routing_version,
            query=request.query,
            mode=request.mode,
            provider=provider,
            model=request.model,
        )
        async with self.engine.begin() as connection:
            await connection.execute(
                insert(jobs).values(
                    id=job.id,
                    rerun_of_job_id=job.rerun_of_job_id,
                    routing_version=job.routing_version,
                    query=job.query,
                    mode=job.mode,
                    provider=job.provider,
                    model=job.model,
                    status=job.status,
                    draft_report=job.draft_report,
                    final_report=job.final_report,
                    error=job.error,
                    error_code=job.error_code,
                    error_retryable=job.error_retryable,
                    error_stage=job.error_stage,
                    retry_context=None,
                    anonymous_id=None if user_id else anonymous_id,
                    user_id=user_id,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
        return job

    async def get_job(
        self,
        job_id: str,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[ResearchJob]:
        await self._ready()
        conditions = [jobs.c.id == job_id]
        owner_clause = self._owner_clause(anonymous_id=anonymous_id, user_id=user_id)
        if owner_clause is not None:
            conditions.append(owner_clause)
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(select(jobs).where(and_(*conditions)))
            ).mappings().first()
        return _job_from_row(row) if row else None

    async def list_jobs(
        self,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchJob]:
        await self._ready()
        statement = select(jobs)
        owner_clause = self._owner_clause(anonymous_id=anonymous_id, user_id=user_id)
        if owner_clause is not None:
            statement = statement.where(owner_clause)
        statement = statement.order_by(jobs.c.updated_at.desc()).limit(limit).offset(offset)
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [_job_from_row(row) for row in rows]

    async def list_events(self, job_id: str) -> list[ResearchEvent]:
        await self._ready()
        statement = (
            select(events)
            .where(events.c.job_id == job_id)
            .order_by(events.c.created_at.asc(), events.c.id.asc())
        )
        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [_event_from_row(row) for row in rows]

    async def add_event(self, event: ResearchEvent) -> None:
        await self._ready()
        now = utc_now()
        values: dict[str, object] = {"updated_at": now}
        if event.type == "completed":
            final_report = event.payload.get("final_report")
            values.update(
                status="completed",
                final_report=final_report,
                draft_report=final_report or jobs.c.draft_report,
                error=None,
                error_code=None,
                error_retryable=False,
                error_stage=None,
            )
        elif event.type == "failed":
            values.update(
                status="failed",
                error=event.message,
                error_code=event.payload.get("error_code"),
                error_retryable=bool(event.payload.get("retryable", False)),
                error_stage=event.payload.get("stage"),
            )
        elif event.type == "cancelled":
            values.update(status="cancelled")
        elif event.type == "report_reset":
            values.update(draft_report="")

        async with self.engine.begin() as connection:
            await connection.execute(
                insert(events).values(
                    id=event.id,
                    job_id=event.job_id,
                    type=event.type,
                    message=event.message,
                    payload=event.payload,
                    created_at=event.created_at,
                )
            )
            await connection.execute(
                update(jobs).where(jobs.c.id == event.job_id).values(**values)
            )

    async def start_job(self, job_id: str) -> bool:
        await self._ready()
        async with self.engine.begin() as connection:
            result = await connection.execute(
                update(jobs)
                .where(and_(jobs.c.id == job_id, jobs.c.status == "queued"))
                .values(
                    status="running",
                    error=None,
                    error_code=None,
                    error_retryable=False,
                    error_stage=None,
                    updated_at=utc_now(),
                )
            )
        return bool(result.rowcount)

    async def request_cancel(
        self,
        job_id: str,
        *,
        anonymous_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[Optional[ResearchJob], bool]:
        await self._ready()
        conditions = [jobs.c.id == job_id, jobs.c.status.in_(("queued", "running"))]
        owner_clause = self._owner_clause(anonymous_id=anonymous_id, user_id=user_id)
        if owner_clause is not None:
            conditions.append(owner_clause)
        async with self.engine.begin() as connection:
            result = await connection.execute(
                update(jobs)
                .where(and_(*conditions))
                .values(status="cancelled", updated_at=utc_now())
            )
        job = await self.get_job(job_id, anonymous_id=anonymous_id, user_id=user_id)
        return job, bool(result.rowcount)

    async def append_report_delta(self, job_id: str, delta: str) -> None:
        if not delta:
            return
        await self._ready()
        async with self.engine.begin() as connection:
            await connection.execute(
                update(jobs)
                .where(
                    and_(
                        jobs.c.id == job_id,
                        jobs.c.status.not_in(("completed", "failed", "cancelled")),
                    )
                )
                .values(
                    draft_report=jobs.c.draft_report + delta,
                    updated_at=utc_now(),
                )
            )

    async def update_status(self, job_id: str, status: str) -> None:
        await self._ready()
        async with self.engine.begin() as connection:
            await connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(status=status, updated_at=utc_now())
            )

    async def save_retry_context(self, job_id: str, context: dict[str, object]) -> None:
        await self._ready()
        async with self.engine.begin() as connection:
            await connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(retry_context=context, updated_at=utc_now())
            )

    async def get_retry_context(self, job_id: str) -> Optional[dict[str, object]]:
        await self._ready()
        async with self.engine.connect() as connection:
            value = await connection.scalar(
                select(jobs.c.retry_context).where(jobs.c.id == job_id)
            )
        return dict(value) if isinstance(value, dict) else None

    async def recover_incomplete_jobs(self) -> int:
        await self._ready()
        now = utc_now()
        failure_message = "研究服务暂时繁忙，请稍后重试。"
        async with self.engine.begin() as connection:
            rows = (
                await connection.execute(
                    select(jobs.c.id).where(jobs.c.status.in_(("queued", "running")))
                )
            ).all()
            job_ids = [row.id for row in rows]
            if not job_ids:
                return 0
            await connection.execute(
                update(jobs)
                .where(jobs.c.id.in_(job_ids))
                .values(
                    status="failed",
                    error=failure_message,
                    error_code="service_unavailable",
                    error_retryable=True,
                    error_stage=None,
                    updated_at=now,
                )
            )
            await connection.execute(
                insert(events),
                [
                    {
                        "id": ResearchEvent(
                            job_id=job_id,
                            type="failed",
                            message=failure_message,
                            payload={
                                "error_code": "service_unavailable",
                                "retryable": True,
                                "stage": None,
                            },
                        ).id,
                        "job_id": job_id,
                        "type": "failed",
                        "message": failure_message,
                        "payload": {
                            "error_code": "service_unavailable",
                            "retryable": True,
                            "stage": None,
                        },
                        "created_at": now,
                    }
                    for job_id in job_ids
                ],
            )
        return len(job_ids)

    async def claim_anonymous_jobs(self, anonymous_id: str, *, user_id: str) -> int:
        await self._ready()
        async with self.engine.begin() as connection:
            result = await connection.execute(
                update(jobs)
                .where(and_(jobs.c.anonymous_id == anonymous_id, jobs.c.user_id.is_(None)))
                .values(anonymous_id=None, user_id=user_id, updated_at=utc_now())
            )
        return int(result.rowcount or 0)
