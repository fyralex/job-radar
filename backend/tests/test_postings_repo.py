from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from job_radar.models import BoardRow, PostingRow
from job_radar.services.location import LocationRule
from job_radar.services.postings_repo import open_postings, upsert_board_postings
from job_radar.sources.common import RawPosting

pytestmark = pytest.mark.db
T0 = datetime(2026, 3, 1, 12, tzinfo=UTC)


def raw(
    title: str, location: str = "Austin, TX", req: str = "1", age: int | None = 3
) -> RawPosting:
    return RawPosting("1", "Acme", "Tech", req, title, location, "", age, f"https://x/{req}")


@pytest.fixture
def board(session: Session) -> BoardRow:
    row = BoardRow(platform="greenhouse", slug="acme", org="Acme", category="Tech", options={})
    session.add(row)
    session.flush()
    return row


def test_first_seen_last_seen_and_closed(session: Session, board: BoardRow) -> None:
    assert upsert_board_postings(session, board.id, [raw("Engineer"), raw("Designer")], T0) == 2

    later = T0 + timedelta(hours=6)
    upsert_board_postings(session, board.id, [raw("Engineer", req="2")], later)
    rows = {r.title: r for r in session.scalars(select(PostingRow))}
    assert rows["Engineer"].first_seen_at == T0
    assert rows["Engineer"].last_seen_at == later
    assert rows["Engineer"].req_id == "2"
    assert rows["Engineer"].closed_at is None
    assert rows["Designer"].closed_at == later

    # Re-listed: open again, first_seen kept.
    upsert_board_postings(session, board.id, [raw("Designer")], later + timedelta(hours=6))
    session.expire_all()
    designer = session.scalars(select(PostingRow).where(PostingRow.title == "Designer")).one()
    assert designer.closed_at is None
    assert designer.first_seen_at == T0


def test_duplicate_listings_collapse(session: Session, board: BoardRow) -> None:
    count = upsert_board_postings(
        session, board.id, [raw("Engineer", req="1"), raw("Engineer", req="2")], T0
    )
    assert count == 1


def test_empty_result_closes_everything(session: Session, board: BoardRow) -> None:
    upsert_board_postings(session, board.id, [raw("Engineer")], T0)
    upsert_board_postings(session, board.id, [], T0 + timedelta(hours=1))
    assert session.scalars(select(PostingRow)).one().closed_at is not None


def test_open_postings_computes_views(session: Session, board: BoardRow) -> None:
    upsert_board_postings(session, board.id, [raw("Engineer", age=3)], T0)
    rule = LocationRule.build(states=["TX"])
    views = open_postings(session, rule, T0.date() + timedelta(days=2), new_since=None)
    assert len(views) == 1
    view = views[0]
    assert view.posted_age_days == 5
    assert view.local
    assert view.work_type == "onsite"
    assert view.category == "Tech"
    assert not view.is_new
    assert open_postings(session, rule, T0.date(), new_since=T0 - timedelta(hours=1))[0].is_new
