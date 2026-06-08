from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.agent.schemas import ResearchEvent, ResearchRequest
from app.storage.migrations import upgrade_database
from app.storage.sql import SqlJobStore


VISITOR_A = "11111111-1111-4111-8111-111111111111"
VISITOR_B = "22222222-2222-4222-8222-222222222222"


def test_sql_store_persists_jobs_events_and_report_drafts(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'research.db'}"

    async def run_scenario():
        first_store = SqlJobStore(database_url)
        await first_store.initialize()
        request = ResearchRequest(query="测试数据库重启恢复", mode="quick", provider="mock")
        job = await first_store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        await first_store.start_job(job.id)
        await first_store.append_report_delta(job.id, "第一段")
        event = ResearchEvent(job_id=job.id, type="status", message="已开始研究")
        await first_store.add_event(event)
        await first_store.dispose()

        second_store = SqlJobStore(database_url)
        await second_store.initialize()
        restored_job = await second_store.get_job(job.id, anonymous_id=VISITOR_A)
        restored_events = await second_store.list_events(job.id)
        history = await second_store.list_jobs(anonymous_id=VISITOR_A)
        await second_store.dispose()
        return job, event, restored_job, restored_events, history

    job, event, restored_job, restored_events, history = asyncio.run(run_scenario())

    assert restored_job is not None
    assert restored_job.id == job.id
    assert restored_job.status == "running"
    assert restored_job.draft_report == "第一段"
    assert [item.id for item in restored_events] == [event.id]
    assert [item.id for item in history] == [job.id]


def test_sql_store_filters_history_and_details_by_owner(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'owners.db'}"

    async def run_scenario():
        store = SqlJobStore(database_url)
        await store.initialize()
        request_a = ResearchRequest(query="访客 A 的研究", mode="quick", provider="mock")
        request_b = ResearchRequest(query="访客 B 的研究", mode="deep", provider="mock")
        job_a = await store.create_job(request_a, provider="mock", anonymous_id=VISITOR_A)
        job_b = await store.create_job(request_b, provider="mock", anonymous_id=VISITOR_B)
        history_a = await store.list_jobs(anonymous_id=VISITOR_A)
        hidden_job = await store.get_job(job_b.id, anonymous_id=VISITOR_A)
        visible_job = await store.get_job(job_a.id, anonymous_id=VISITOR_A)
        await store.dispose()
        return job_a, history_a, hidden_job, visible_job

    job_a, history_a, hidden_job, visible_job = asyncio.run(run_scenario())

    assert [item.id for item in history_a] == [job_a.id]
    assert hidden_job is None
    assert visible_job is not None
    assert visible_job.id == job_a.id


def test_sql_store_marks_incomplete_jobs_failed_after_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}"

    async def run_scenario():
        store = SqlJobStore(database_url)
        await store.initialize()
        request = ResearchRequest(query="测试异常重启恢复", mode="quick", provider="mock")
        queued = await store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        running = await store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        completed = await store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        await store.start_job(running.id)
        await store.add_event(
            ResearchEvent(
                job_id=completed.id,
                type="completed",
                message="研究报告已生成",
                payload={"final_report": "完成", "sources": []},
            )
        )

        recovered_count = await store.recover_incomplete_jobs()
        queued_after = await store.get_job(queued.id)
        running_after = await store.get_job(running.id)
        completed_after = await store.get_job(completed.id)
        queued_events = await store.list_events(queued.id)
        running_events = await store.list_events(running.id)
        await store.dispose()
        return (
            recovered_count,
            queued_after,
            running_after,
            completed_after,
            queued_events,
            running_events,
        )

    (
        recovered_count,
        queued_after,
        running_after,
        completed_after,
        queued_events,
        running_events,
    ) = asyncio.run(run_scenario())

    assert recovered_count == 2
    assert queued_after is not None and queued_after.status == "failed"
    assert running_after is not None and running_after.status == "failed"
    assert completed_after is not None and completed_after.status == "completed"
    assert queued_events[-1].type == "failed"
    assert running_events[-1].type == "failed"
    assert "服务重启" in queued_events[-1].message


def test_sql_store_can_claim_anonymous_history_for_future_user_account(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'claim.db'}"

    async def run_scenario():
        store = SqlJobStore(database_url)
        await store.initialize()
        request = ResearchRequest(query="稍后归并到账号", mode="quick", provider="mock")
        job = await store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        claimed_count = await store.claim_anonymous_jobs(VISITOR_A, user_id="user-123")
        anonymous_history = await store.list_jobs(anonymous_id=VISITOR_A)
        user_history = await store.list_jobs(user_id="user-123")
        await store.dispose()
        return job, claimed_count, anonymous_history, user_history

    job, claimed_count, anonymous_history, user_history = asyncio.run(run_scenario())

    assert claimed_count == 1
    assert anonymous_history == []
    assert [item.id for item in user_history] == [job.id]


def test_alembic_upgrade_creates_versioned_product_schema(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'migrated.db'}"

    async def run_scenario():
        await upgrade_database(database_url)
        store = SqlJobStore(database_url, auto_create_schema=False)
        await store.initialize()
        request = ResearchRequest(query="迁移后创建任务", mode="quick", provider="mock")
        job = await store.create_job(request, provider="mock", anonymous_id=VISITOR_A)
        async with store.engine.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await store.dispose()
        return job, version

    job, version = asyncio.run(run_scenario())

    assert job.query == "迁移后创建任务"
    assert version == "20260608_01"


def test_alembic_upgrade_baselines_matching_unversioned_schema(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}"

    async def run_scenario():
        legacy_store = SqlJobStore(database_url)
        await legacy_store.initialize()
        await legacy_store.dispose()

        await upgrade_database(database_url)
        migrated_store = SqlJobStore(database_url, auto_create_schema=False)
        await migrated_store.initialize()
        async with migrated_store.engine.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await migrated_store.dispose()
        return version

    assert asyncio.run(run_scenario()) == "20260608_01"
