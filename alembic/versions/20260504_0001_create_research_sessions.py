"""create research_sessions

Revision ID: 20260504_0001
Revises:
Create Date: 2026-05-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260504_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("search_queries", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("arxiv_count", sa.Integer(), nullable=False),
        sa.Column("web_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("research_sessions")
