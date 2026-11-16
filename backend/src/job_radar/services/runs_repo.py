"""Scrape run history: one row per board per run, kept for `KEEP_DAYS`.

`refresh.run_scrape` records a row for every board it fetched (not for a
board skipped because another process held its lock) and prunes old rows at
the end of the run. The API shows each board's last few runs.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from job_radar.models import ScrapeRunRow

KEEP_DAYS = 30
RECENT_RUNS = 5


def record_run(
    session: Session,
    board_id: int,
    *,
    started_at: datetime,
    finished_at: datetime,
    count: int | None,
    error: str | None,
) -> ScrapeRunRow:
    row = ScrapeRunRow(
        board_id=board_id,
        started_at=started_at,
        finished_at=finished_at,
        status="error" if error is not None else "ok",
        count=count,
        error=error,
    )
    session.add(row)
    return row


def prune_runs(session: Session, now: datetime, keep_days: int = KEEP_DAYS) -> int:
    """Delete runs that started more than `keep_days` ago; returns how many."""
    result = session.execute(
        delete(ScrapeRunRow).where(ScrapeRunRow.started_at < now - timedelta(days=keep_days))
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def recent_runs(
    session: Session, board_ids: Collection[int] | None = None, per_board: int = RECENT_RUNS
) -> dict[int, list[ScrapeRunRow]]:
    """Each board's last `per_board` runs, oldest first, in one query."""
    newest_first = (
        func.row_number()
        .over(
            partition_by=ScrapeRunRow.board_id,
            order_by=(ScrapeRunRow.started_at.desc(), ScrapeRunRow.id.desc()),
        )
        .label("n")
    )
    ranked = select(ScrapeRunRow.id, newest_first)
    if board_ids is not None:
        ranked = ranked.where(ScrapeRunRow.board_id.in_(list(board_ids)))
    sub = ranked.subquery()
    query = (
        select(ScrapeRunRow)
        .join(sub, sub.c.id == ScrapeRunRow.id)
        .where(sub.c.n <= per_board)
        .order_by(ScrapeRunRow.board_id, ScrapeRunRow.started_at, ScrapeRunRow.id)
    )
    runs: dict[int, list[ScrapeRunRow]] = {}
    for row in session.scalars(query):
        runs.setdefault(row.board_id, []).append(row)
    return runs


def run_json(row: ScrapeRunRow) -> dict[str, Any]:
    return {
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat(),
        "status": row.status,
        "count": row.count,
        "error": row.error,
    }
