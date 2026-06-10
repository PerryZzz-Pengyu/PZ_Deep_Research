"""create persistent research jobs and events

Revision ID: 20260608_01
Revises:
Create Date: 2026-06-08 20:20:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260608_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JOB_COLUMNS = {
    "id",
    "query",
    "mode",
    "provider",
    "model",
    "status",
    "draft_report",
    "final_report",
    "error",
    "anonymous_id",
    "user_id",
    "created_at",
    "updated_at",
}
EVENT_COLUMNS = {"id", "job_id", "type", "message", "payload", "created_at"}


def _validate_existing_table(inspector, table_name: str, expected_columns: set[str]) -> None:
    actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if not expected_columns.issubset(actual_columns):
        raise RuntimeError(
            f"Existing table {table_name} does not match the expected baseline schema. "
            f"Required {sorted(expected_columns)}, got {sorted(actual_columns)}."
        )


def _create_index_if_missing(inspector, name: str, table_name: str, columns: list[str]) -> None:
    if inspector is None or name not in {
        index["name"] for index in inspector.get_indexes(table_name)
    }:
        op.create_index(name, table_name, columns, unique=False)


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    existing_tables = set() if inspector is None else set(inspector.get_table_names())

    if "research_jobs" not in existing_tables:
        op.create_table(
            "research_jobs",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("model", sa.String(length=160), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("draft_report", sa.Text(), nullable=False),
            sa.Column("final_report", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("anonymous_id", sa.String(length=128), nullable=True),
            sa.Column("user_id", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        _validate_existing_table(inspector, "research_jobs", JOB_COLUMNS)

    _create_index_if_missing(
        inspector,
        "ix_research_jobs_anonymous_updated",
        "research_jobs",
        ["anonymous_id", "updated_at"],
    )
    _create_index_if_missing(
        inspector,
        "ix_research_jobs_user_updated",
        "research_jobs",
        ["user_id", "updated_at"],
    )

    if "research_events" not in existing_tables:
        op.create_table(
            "research_events",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("job_id", sa.String(length=32), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["research_jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        _validate_existing_table(inspector, "research_events", EVENT_COLUMNS)

    _create_index_if_missing(
        inspector,
        "ix_research_events_job_created",
        "research_events",
        ["job_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_events_job_created", table_name="research_events")
    op.drop_table("research_events")
    op.drop_index("ix_research_jobs_user_updated", table_name="research_jobs")
    op.drop_index("ix_research_jobs_anonymous_updated", table_name="research_jobs")
    op.drop_table("research_jobs")
