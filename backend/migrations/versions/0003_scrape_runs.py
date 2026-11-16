"""scrape runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16 00:43:27.391292
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scrape_runs_board_started", "scrape_runs", ["board_id", "started_at"], unique=False
    )
    op.create_index(op.f("ix_scrape_runs_started_at"), "scrape_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scrape_runs_started_at"), table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_board_started", table_name="scrape_runs")
    op.drop_table("scrape_runs")
