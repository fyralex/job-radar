"""One scrape run: fetch the enabled boards, store results, record each board's
outcome. Used by the scheduled worker and the "Refresh now" button.

Only one run happens at a time: the run lock (see `coordination`) is shared
through Redis by the worker, the API and `flask scrape`. Each board is also
fetched under its own lock; a board skipped because another process holds it
is left untouched, like a board that wasn't in the run.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from job_radar.coordination import (
    LOCAL_LOCKS,
    RUN_LOCK,
    RUN_LOCK_TTL_SECONDS,
    Locks,
)
from job_radar.db import session_scope
from job_radar.http import HttpClient
from job_radar.models import BoardRow, utcnow
from job_radar.services.boards_repo import to_board
from job_radar.services.postings_repo import upsert_board_postings
from job_radar.services.scraper import ClientFactory, fetch_boards
from job_radar.services.settings_repo import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSummary:
    boards: int
    failed: int
    postings: int
    finished_at: datetime
    skipped: int = 0


def is_running(locks: Locks = LOCAL_LOCKS) -> bool:
    return locks.held(RUN_LOCK)


def run_scrape(
    factory: sessionmaker[Session],
    contact_url: str | None,
    workers: int = 8,
    *,
    board_ids: Collection[int] | None = None,
    client_factory: ClientFactory | None = None,
    locks: Locks = LOCAL_LOCKS,
) -> RunSummary | None:
    """Scrape now. Returns None if a run is already in progress anywhere (or
    Redis is unreachable, so the run lock can't be taken)."""
    token = locks.acquire(RUN_LOCK, RUN_LOCK_TTL_SECONDS)
    if token is None:
        return None
    return _run_holding_lock(
        factory,
        contact_url,
        workers=workers,
        board_ids=board_ids,
        client_factory=client_factory,
        locks=locks,
        token=token,
    )


def _run_holding_lock(
    factory: sessionmaker[Session],
    contact_url: str | None,
    *,
    workers: int,
    board_ids: Collection[int] | None,
    client_factory: ClientFactory | None,
    locks: Locks,
    token: str,
) -> RunSummary:
    """The run itself, by a caller that already holds the run lock (`token`).
    Releases the lock when done."""
    try:
        with session_scope(factory) as session:
            stmt = select(BoardRow).where(BoardRow.enabled.is_(True))
            if board_ids is not None:
                stmt = stmt.where(BoardRow.id.in_(list(board_ids)))
            boards = [to_board(row) for row in session.scalars(stmt)]

        results = fetch_boards(
            boards,
            client_factory or (lambda: HttpClient(contact_url)),
            workers=workers,
            locks=locks,
        )

        now = utcnow()
        total = failed = skipped = 0
        with session_scope(factory) as session:
            for result in results:
                if result.skipped:
                    skipped += 1
                    logger.info(
                        "board %s skipped: its lock is held elsewhere or Redis is down",
                        result.board.key,
                    )
                    continue
                row = session.get(BoardRow, int(result.board.key))
                if row is None:  # deleted while the run was in progress
                    continue
                row.last_scraped_at = now
                if result.ok:
                    count = upsert_board_postings(session, row.id, result.postings, now)
                    row.last_status, row.last_error, row.last_count = "ok", None, count
                    total += count
                else:
                    failed += 1
                    row.last_status, row.last_error = "error", (result.error or "")[:2000]
                    logger.warning("board %s (%s) failed: %s", row.id, row.org, result.error)
            # A run that fetched nothing (no boards yet, or every board skipped)
            # hasn't really scraped: keep it due so the worker tries again soon.
            if board_ids is None and skipped < len(results):
                get_settings(session).last_full_scrape_at = now
        return RunSummary(len(results), failed, total, now, skipped)
    finally:
        locks.release(RUN_LOCK, token)


def scrape_due(last_full_scrape_at: datetime | None, interval_hours: int, now: datetime) -> bool:
    return last_full_scrape_at is None or now - last_full_scrape_at >= timedelta(
        hours=interval_hours
    )


def start_in_background(
    factory: sessionmaker[Session],
    contact_url: str | None,
    workers: int = 8,
    board_ids: Collection[int] | None = None,
    locks: Locks = LOCAL_LOCKS,
) -> bool:
    """Kick off a run on a daemon thread. False if one is already running, or
    if Redis is down so the run lock can't be taken. The lock is taken here,
    before the thread starts, so "started" always means a run is happening."""
    token = locks.acquire(RUN_LOCK, RUN_LOCK_TTL_SECONDS)
    if token is None:
        return False
    thread = threading.Thread(
        target=_run_holding_lock,
        args=(factory, contact_url),
        kwargs={
            "workers": workers,
            "board_ids": board_ids,
            "client_factory": None,
            "locks": locks,
            "token": token,
        },
        name="scrape",
        daemon=True,
    )
    thread.start()
    return True
