"""One scrape run: fetch the enabled boards, store results, record each board's
outcome. Used by the scheduled worker and the "Refresh now" button.

Only one run happens at a time per process (`_RUN_LOCK`). The worker container
and the API process each have their own lock until the Redis lock arrives;
a double run costs requests, not correctness, since upserts are idempotent.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from job_radar.db import session_scope
from job_radar.http import HttpClient
from job_radar.models import BoardRow, utcnow
from job_radar.services.boards_repo import to_board
from job_radar.services.postings_repo import upsert_board_postings
from job_radar.services.scraper import ClientFactory, fetch_boards
from job_radar.services.settings_repo import get_settings

logger = logging.getLogger(__name__)

_RUN_LOCK = threading.Lock()


@dataclass(frozen=True)
class RunSummary:
    boards: int
    failed: int
    postings: int
    finished_at: datetime


def is_running() -> bool:
    return _RUN_LOCK.locked()


def run_scrape(
    factory: sessionmaker[Session],
    contact_url: str | None,
    workers: int = 8,
    board_ids: Collection[int] | None = None,
    client_factory: ClientFactory | None = None,
) -> RunSummary | None:
    """Scrape now. Returns None if a run is already in progress here."""
    if not _RUN_LOCK.acquire(blocking=False):
        return None
    try:
        with session_scope(factory) as session:
            stmt = select(BoardRow).where(BoardRow.enabled.is_(True))
            if board_ids is not None:
                stmt = stmt.where(BoardRow.id.in_(list(board_ids)))
            boards = [to_board(row) for row in session.scalars(stmt)]

        results = fetch_boards(
            boards, client_factory or (lambda: HttpClient(contact_url)), workers=workers
        )

        now = utcnow()
        total = failed = 0
        with session_scope(factory) as session:
            for result in results:
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
            # An install with no boards yet hasn't really scraped: keep it due.
            if board_ids is None and results:
                get_settings(session).last_full_scrape_at = now
        return RunSummary(len(results), failed, total, now)
    finally:
        _RUN_LOCK.release()


def scrape_due(last_full_scrape_at: datetime | None, interval_hours: int, now: datetime) -> bool:
    return last_full_scrape_at is None or now - last_full_scrape_at >= timedelta(
        hours=interval_hours
    )


def start_in_background(
    factory: sessionmaker[Session],
    contact_url: str | None,
    workers: int = 8,
    board_ids: Collection[int] | None = None,
) -> bool:
    """Kick off a run on a daemon thread. False if one is already running."""
    if is_running():
        return False
    thread = threading.Thread(
        target=run_scrape,
        args=(factory, contact_url, workers, board_ids),
        name="scrape",
        daemon=True,
    )
    thread.start()
    return True
