from __future__ import annotations

from datetime import timedelta

import pytest
import responses
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from job_radar.coordination import LocalLocks, board_lock
from job_radar.http import HostThrottle, HttpClient, RobotsCache
from job_radar.models import BoardRow, ScrapeRunRow, utcnow
from job_radar.services.refresh import run_scrape
from job_radar.services.runs_repo import prune_runs, recent_runs, record_run
from tests.conftest import fixture_json

pytestmark = pytest.mark.db
GREENHOUSE = "https://boards-api.greenhouse.io"


def _client() -> HttpClient:
    return HttpClient(
        robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=lambda _s: None
    )


def _board(session: Session, slug: str) -> BoardRow:
    row = BoardRow(platform="greenhouse", slug=slug, org=slug.title(), options={})
    session.add(row)
    session.flush()
    return row


def _runs(session: Session, board: BoardRow, ages_hours: list[float]) -> None:
    now = utcnow()
    for age in ages_hours:
        start = now - timedelta(hours=age)
        record_run(
            session, board.id, started_at=start, finished_at=start, count=int(age), error=None
        )
    session.flush()


def test_recent_runs_keeps_the_last_few_oldest_first(session: Session) -> None:
    a, b = _board(session, "a"), _board(session, "b")
    _runs(session, a, [1, 2, 3, 4, 5, 6, 7])
    _runs(session, b, [10])
    runs = recent_runs(session, per_board=5)
    assert [r.count for r in runs[a.id]] == [5, 4, 3, 2, 1]
    assert [r.count for r in runs[b.id]] == [10]
    assert list(recent_runs(session, [b.id])) == [b.id]


def test_record_run_sets_the_status(session: Session) -> None:
    board = _board(session, "a")
    now = utcnow()
    ok = record_run(session, board.id, started_at=now, finished_at=now, count=3, error=None)
    bad = record_run(session, board.id, started_at=now, finished_at=now, count=None, error="404")
    assert (ok.status, bad.status) == ("ok", "error")


def test_prune_keeps_thirty_days(session: Session) -> None:
    board = _board(session, "a")
    _runs(session, board, [1, 24 * 29, 24 * 31, 24 * 60])
    assert prune_runs(session, utcnow()) == 2
    left = session.scalars(select(ScrapeRunRow.count).order_by(ScrapeRunRow.count)).all()
    assert left == [1, 24 * 29]


def test_runs_go_with_their_board(session: Session) -> None:
    board = _board(session, "a")
    _runs(session, board, [1, 2])
    session.delete(board)
    session.flush()
    assert session.scalar(select(func.count()).select_from(ScrapeRunRow)) == 0


@responses.activate
def test_a_scrape_records_one_run_per_fetched_board(
    sessions: sessionmaker[Session], session: Session
) -> None:
    good, gone, busy = _board(session, "good"), _board(session, "gone"), _board(session, "busy")
    session.commit()
    responses.get(f"{GREENHOUSE}/robots.txt", status=404)
    responses.get(f"{GREENHOUSE}/v1/boards/good/jobs", json=fixture_json("greenhouse.json"))
    responses.get(f"{GREENHOUSE}/v1/boards/gone/jobs", status=404)
    locks = LocalLocks()
    assert locks.acquire(board_lock(str(busy.id)), 60) is not None  # being scraped elsewhere

    summary = run_scrape(sessions, None, client_factory=_client, locks=locks)

    assert summary is not None
    runs = recent_runs(session)
    assert set(runs) == {good.id, gone.id}  # the skipped board gets no row
    [ok] = runs[good.id]
    assert (ok.status, ok.count, ok.error) == ("ok", 4, None)
    assert ok.finished_at == summary.finished_at and ok.started_at <= ok.finished_at
    [failed] = runs[gone.id]
    assert failed.status == "error" and failed.count is None and "404" in (failed.error or "")


def test_a_scrape_prunes_old_runs(sessions: sessionmaker[Session], session: Session) -> None:
    board = _board(session, "a")
    _runs(session, board, [24 * 40])
    session.commit()
    run_scrape(sessions, None, client_factory=_client, board_ids=[])
    assert session.scalar(select(func.count()).select_from(ScrapeRunRow)) == 0


def test_boards_api_includes_recent_runs(api: FlaskClient, session: Session) -> None:
    created = api.post(
        "/api/boards", json={"platform": "greenhouse", "slug": "acme", "org": "Acme"}
    ).json
    assert created["recent_runs"] == []
    board = session.get(BoardRow, created["id"])
    assert board is not None
    _runs(session, board, [2, 1])
    now = utcnow()
    record_run(session, board.id, started_at=now, finished_at=now, count=None, error="HTTP 500")
    session.flush()

    [listed] = api.get("/api/boards").json
    assert [r["status"] for r in listed["recent_runs"]] == ["ok", "ok", "error"]
    assert listed["recent_runs"][-1]["error"] == "HTTP 500"
    assert set(listed["recent_runs"][0]) == {
        "started_at",
        "finished_at",
        "status",
        "count",
        "error",
    }

    patched = api.patch(f"/api/boards/{board.id}", json={"category": "Tech"}).json
    assert len(patched["recent_runs"]) == 3
