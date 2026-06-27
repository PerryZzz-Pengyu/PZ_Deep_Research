"""add research domain to jobs

Revision ID: 20260628_06
Revises: 20260613_05
Create Date: 2026-06-28 02:00:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260628_06"
down_revision: Union[str, Sequence[str], None] = "20260613_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    column_names = (
        set()
        if inspector is None
        else {column["name"] for column in inspector.get_columns("research_jobs")}
    )
    if inspector is None or "domain" not in column_names:
        op.add_column(
            "research_jobs",
            sa.Column(
                "domain",
                sa.String(length=32),
                nullable=False,
                server_default="academic",
            ),
        )


def downgrade() -> None:
    op.drop_column("research_jobs", "domain")
