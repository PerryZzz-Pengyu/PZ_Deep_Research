"""add model routing version

Revision ID: 20260611_04
Revises: 20260610_03
Create Date: 2026-06-11 00:30:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260611_04"
down_revision: Union[str, Sequence[str], None] = "20260610_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    column_names = (
        set()
        if inspector is None
        else {column["name"] for column in inspector.get_columns("research_jobs")}
    )
    if inspector is None or "routing_version" not in column_names:
        op.add_column(
            "research_jobs",
            sa.Column("routing_version", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("research_jobs", "routing_version")
