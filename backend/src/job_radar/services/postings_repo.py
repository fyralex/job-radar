"""Store scrape results and read them back for the dashboard.

`upsert_board_postings` is called once per successfully fetched board:
- New posting_key: inserted with first_seen_at = now.
- Seen again: fields refreshed, last_seen_at = now, closed_at cleared.
- Previously open on this board but missing now: closed_at = now (kept for
  history, hidden from the dashboard).
A failed board is not touched, so a temporary outage never closes its jobs.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from job_radar.models import BoardRow, PostingRow
from job_radar.services.filters import PostingView, make_view, posting_key
from job_radar.services.location import LocationRule
from job_radar.sources.common import RawPosting


def _posted_on(posting: RawPosting, today: date) -> date | None:
    if posting.posted_age_days is None:
        return None
    return today - timedelta(days=posting.posted_age_days)


def upsert_board_postings(
    session: Session, board_id: int, postings: Sequence[RawPosting], now: datetime
) -> int:
    """Returns how many unique postings the board has now."""
    rows: dict[str, dict[str, object]] = {}
    today = now.date()
    for p in postings:
        key = posting_key(p.org, p.title, p.location)
        rows.setdefault(
            key,
            {
                "posting_key": key,
                "board_id": board_id,
                "req_id": p.req_id[:200],
                "org": p.org[:200],
                "title": p.title[:500],
                "location": p.location,
                "url": p.url,
                "posted_raw": p.posted_raw[:100],
                "posted_on": _posted_on(p, today),
                "workplace": p.workplace,
                "employment_type": p.employment_type,
                "first_seen_at": now,
                "last_seen_at": now,
                "closed_at": None,
            },
        )
    values = list(rows.values())
    for start in range(0, len(values), 500):
        stmt = insert(PostingRow).values(values[start : start + 500])
        stmt = stmt.on_conflict_do_update(
            index_elements=[PostingRow.posting_key],
            set_={
                "board_id": stmt.excluded.board_id,
                "req_id": stmt.excluded.req_id,
                "url": stmt.excluded.url,
                "posted_raw": stmt.excluded.posted_raw,
                "posted_on": stmt.excluded.posted_on,
                "workplace": stmt.excluded.workplace,
                "employment_type": stmt.excluded.employment_type,
                "last_seen_at": stmt.excluded.last_seen_at,
                "closed_at": None,
            },
        )
        session.execute(stmt)
    session.execute(
        update(PostingRow)
        .where(
            PostingRow.board_id == board_id,
            PostingRow.closed_at.is_(None),
            PostingRow.posting_key.not_in(list(rows)) if rows else PostingRow.id.is_not(None),
        )
        .values(closed_at=now)
    )
    return len(rows)


def open_postings(
    session: Session, rule: LocationRule, today: date, new_since: datetime | None
) -> list[PostingView]:
    stmt = (
        select(PostingRow, BoardRow.category)
        .join(BoardRow, BoardRow.id == PostingRow.board_id)
        .where(PostingRow.closed_at.is_(None), BoardRow.enabled.is_(True))
    )
    views: list[PostingView] = []
    for row, category in session.execute(stmt).tuples():
        views.append(
            make_view(
                id=row.id,
                posting_key=row.posting_key,
                board_id=row.board_id,
                org=row.org,
                category=category,
                title=row.title,
                location=row.location,
                url=row.url,
                posted_on=row.posted_on,
                workplace=row.workplace,
                employment_type=row.employment_type,
                first_seen_at=row.first_seen_at,
                rule=rule,
                today=today,
                new_since=new_since,
            )
        )
    return views
