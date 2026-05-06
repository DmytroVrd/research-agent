"""add core_entities

Revision ID: 20260505_0004
Revises: 20260505_0003
Create Date: 2026-05-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260505_0004"
down_revision: str | None = "20260505_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_sessions",
        sa.Column("core_entities", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_sessions", "core_entities")
