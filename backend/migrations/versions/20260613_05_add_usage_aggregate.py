"""add per-job usage aggregate

Revision ID: 20260613_05
Revises: 20260611_04
Create Date: 2026-06-13 23:40:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260613_05"
down_revision: Union[str, Sequence[str], None] = "20260611_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USAGE_COLUMNS = (
    "usage_input_tokens",
    "usage_output_tokens",
    "usage_llm_calls",
    "usage_tool_calls",
)


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    existing = (
        set()
        if inspector is None
        else {column["name"] for column in inspector.get_columns("research_jobs")}
    )
    for name in USAGE_COLUMNS:
        if inspector is None or name not in existing:
            op.add_column(
                "research_jobs",
                sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    for name in reversed(USAGE_COLUMNS):
        op.drop_column("research_jobs", name)
