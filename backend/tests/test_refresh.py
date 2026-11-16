from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import responses
from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from job_radar.coordination import RUN_LOCK, LocalLocks, RedisLocks, board_lock
from job_radar.http import HostThrottle, HttpClient, RobotsCache
from job_radar.models import BoardRow, PostingRow
from job_radar.services.refresh import is_running, run_scrape, start_in_background
from job_radar.services.settings_repo import get_settings
from tests.conftest import fixture_json

pytestmark = pytest.mark.db


def _client() -> HttpClient:
    return HttpClient(
        robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=lambda _s: None
    )


@responses.activate
def test_run_scrape_stores_results_and_board_status(
    sessions: sessionmaker[Session], session: Session
) -> None:
    good = BoardRow(platform="greenhouse", slug="good", org="Good Co", options={})
    gone = BoardRow(platform="greenhouse", slug="gone", org="Gone Co", options={})
    off = BoardRow(platform="greenhouse", slug="off", org="Off Co", options={}, enabled=False)
    session.add_all([good, gone, off])
    session.commit()
    responses.get("https://boards-api.greenhouse.io/robots.txt", status=404)
    responses.get(
        "https://boards-api.greenhouse.io/v1/boards/good/jobs", json=fixture_json("greenhouse.json")
    )
    responses.get("https://boards-api.greenhouse.io/v1/boards/gone/jobs", status=404)

    summary = run_scrape(sessions, None, workers=2, client_factory=_client)

    assert summary is not None
    assert (summary.boards, summary.failed, summary.postings) == (2, 1, 4)
    session.expire_all()
    assert session.get(BoardRow, good.id).last_status == "ok"  # type: ignore[union-attr]
    failed = session.get(BoardRow, gone.id)
    assert (
        failed is not None and failed.last_status == "error" and "404" in (failed.last_error or "")
    )
    assert session.get(BoardRow, off.id).last_scraped_at is None  # type: ignore[union-attr]
    assert len(session.scalars(select(PostingRow)).all()) == 4
    assert get_settings(session).last_full_scrape_at == summary.finished_at


@responses.activate
def test_failed_board_keeps_its_open_postings(
    sessions: sessionmaker[Session], session: Session
) -> None:
    board = BoardRow(platform="greenhouse", slug="flaky", org="Flaky", options={})
    session.add(board)
    session.commit()
    responses.get("https://boards-api.greenhouse.io/robots.txt", status=404)
    url = "https://boards-api.greenhouse.io/v1/boards/flaky/jobs"
    responses.get(url, json=fixture_json("greenhouse.json"))
    run_scrape(sessions, None, client_factory=_client)
    responses.replace(responses.GET, url, status=500)
    run_scrape(sessions, None, client_factory=_client)
    session.expire_all()
    rows = session.scalars(select(PostingRow)).all()
    assert len(rows) == 4
    assert all(r.closed_at is None for r in rows)


def test_run_waits_for_the_run_lock(sessions: sessionmaker[Session]) -> None:
    locks = LocalLocks()
    token = locks.acquire(RUN_LOCK, 60)
    assert token is not None and is_running(locks)
    assert run_scrape(sessions, None, client_factory=_client, locks=locks) is None
    locks.release(RUN_LOCK, token)
    assert run_scrape(sessions, None, client_factory=_client, locks=locks) is not None
    assert not is_running(locks)  # released after the run


@pytest.mark.redis
@responses.activate
def test_board_locked_elsewhere_is_skipped_and_left_alone(
    sessions: sessionmaker[Session], session: Session, redis_url: str
) -> None:
    busy = BoardRow(platform="greenhouse", slug="busy", org="Busy", options={})
    free = BoardRow(platform="greenhouse", slug="free", org="Free", options={})
    session.add_all([busy, free])
    session.commit()
    responses.get("https://boards-api.greenhouse.io/robots.txt", status=404)
    responses.get(
        "https://boards-api.greenhouse.io/v1/boards/free/jobs", json=fixture_json("greenhouse.json")
    )
    # Another process is scraping "busy" right now.
    other = RedisLocks.from_url(redis_url)
    assert other.acquire(board_lock(str(busy.id)), 60) is not None

    summary = run_scrape(
        sessions, None, client_factory=_client, locks=RedisLocks.from_url(redis_url)
    )

    assert summary is not None
    assert (summary.boards, summary.failed, summary.skipped) == (2, 0, 1)
    session.expire_all()
    skipped = session.get(BoardRow, busy.id)
    assert skipped is not None and skipped.last_scraped_at is None and skipped.last_status is None
    assert session.get(BoardRow, free.id).last_status == "ok"  # type: ignore[union-attr]
    # Only "busy"'s jobs URL was never requested.
    assert not any("/boards/busy/" in c.request.url for c in responses.calls)
    assert not other.held(RUN_LOCK)


def test_run_where_every_board_was_skipped_stays_due(
    sessions: sessionmaker[Session], session: Session
) -> None:
    # E.g. Redis dropped after the run lock was taken: no board lock could be had.
    board = BoardRow(platform="greenhouse", slug="busy", org="Busy", options={})
    session.add(board)
    session.commit()
    locks = LocalLocks()
    assert locks.acquire(board_lock(str(board.id)), 60) is not None
    summary = run_scrape(sessions, None, client_factory=_client, locks=locks)
    assert summary is not None and summary.skipped == 1
    assert get_settings(session).last_full_scrape_at is None


def test_start_in_background_takes_the_lock_first(sessions: sessionmaker[Session]) -> None:
    locks = LocalLocks()
    token = locks.acquire(RUN_LOCK, 60)
    assert token is not None
    assert start_in_background(sessions, None, locks=locks) is False
    locks.release(RUN_LOCK, token)

    assert start_in_background(sessions, None, locks=locks) is True
    # The thread releases the lock when its (empty) run ends.
    deadline = time.monotonic() + 5
    while is_running(locks) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not is_running(locks)


def test_start_in_background_releases_the_lock_if_the_thread_cannot_start(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_self: threading.Thread) -> None:
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", fail)
    locks = LocalLocks()
    with pytest.raises(RuntimeError):
        start_in_background(sessions, None, locks=locks)
    assert not is_running(locks)


def test_start_in_background_refuses_when_redis_is_down(
    sessions: sessionmaker[Session],
) -> None:
    assert (
        start_in_background(sessions, None, locks=RedisLocks.from_url("redis://127.0.0.1:1/0"))
        is False
    )


def test_no_boards_does_not_count_as_a_full_scrape(
    sessions: sessionmaker[Session], session: Session
) -> None:
    summary = run_scrape(sessions, None, client_factory=_client)
    assert summary is not None and summary.boards == 0
    assert get_settings(session).last_full_scrape_at is None


def test_boards_import_command(app: Flask, session: Session, tmp_path: Path) -> None:
    path = tmp_path / "boards.yaml"
    path.write_text(
        "boards:\n"
        "  - {platform: greenhouse, slug: acme, org: Acme, category: Tech}\n"
        "  - {platform: lever, slug: other, org: Other, options: {undated: true}}\n",
        encoding="utf-8",
    )
    runner = app.test_cli_runner()
    first = runner.invoke(args=["boards", "import", str(path)])
    assert "added 2 boards" in first.output, first.output
    second = runner.invoke(args=["boards", "import", str(path)])
    assert "added 0 boards, skipped 2" in second.output
    lever_board = session.scalars(select(BoardRow).where(BoardRow.platform == "lever")).one()
    assert lever_board.options == {"undated": True}


def test_boards_import_rejects_bad_file(app: Flask, tmp_path: Path) -> None:
    path = tmp_path / "boards.yaml"
    path.write_text("boards:\n  - {platform: myspace, slug: x, org: X}\n", encoding="utf-8")
    result = app.test_cli_runner().invoke(args=["boards", "import", str(path)])
    assert result.exit_code != 0
