"""add rerun lineage to research jobs

Revision ID: 20260609_02
Revises: 20260608_01
Create Date: 2026-06-09 11:20:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260609_02"
down_revision: Union[str, Sequence[str], None] = "20260608_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    column_names = (
        set()
        if inspector is None
        else {column["name"] for column in inspector.get_columns("research_jobs")}
    )
    if inspector is None or "rerun_of_job_id" not in column_names:
        op.add_column(
            "research_jobs",
            sa.Column("rerun_of_job_id", sa.String(length=32), nullable=True),
        )

    index_names = (
        set()
        if inspector is None
        else {index["name"] for index in inspector.get_indexes("research_jobs")}
    )
    if inspector is None or "ix_research_jobs_rerun_of" not in index_names:
        op.create_index(
            "ix_research_jobs_rerun_of",
            "research_jobs",
            ["rerun_of_job_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_research_jobs_rerun_of", table_name="research_jobs")
    op.drop_column("research_jobs", "rerun_of_job_id")
