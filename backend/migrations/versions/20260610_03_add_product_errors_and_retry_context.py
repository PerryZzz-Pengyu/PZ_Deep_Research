"""add product error metadata and retry checkpoint

Revision ID: 20260610_03
Revises: 20260609_02
Create Date: 2026-06-10 20:00:00
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "20260610_03"
down_revision: Union[str, Sequence[str], None] = "20260609_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    column_names = (
        set()
        if inspector is None
        else {column["name"] for column in inspector.get_columns("research_jobs")}
    )
    columns = (
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "error_retryable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("error_stage", sa.String(length=32), nullable=True),
        sa.Column("retry_context", sa.JSON(), nullable=True),
    )
    for column in columns:
        if inspector is None or column.name not in column_names:
            op.add_column("research_jobs", column)


def downgrade() -> None:
    op.drop_column("research_jobs", "retry_context")
    op.drop_column("research_jobs", "error_stage")
    op.drop_column("research_jobs", "error_retryable")
    op.drop_column("research_jobs", "error_code")
