from __future__ import annotations

from datetime import UTC, datetime, timedelta

import responses

from job_radar.http import HostThrottle, HttpClient, RobotsCache
from job_radar.services.refresh import scrape_due
from job_radar.services.scraper import fetch_boards
from job_radar.sources.common import Board
from tests.conftest import fixture_json


def _client() -> HttpClient:
    return HttpClient(
        robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=lambda _s: None
    )


@responses.activate
def test_one_failing_board_does_not_stop_the_others() -> None:
    responses.get("https://boards-api.greenhouse.io/robots.txt", status=404)
    responses.get(
        "https://boards-api.greenhouse.io/v1/boards/good/jobs", json=fixture_json("greenhouse.json")
    )
    responses.get("https://boards-api.greenhouse.io/v1/boards/gone/jobs", status=404)
    responses.get("https://boards-api.greenhouse.io/v1/boards/broken/jobs", json={"x": 1})
    boards = [
        Board(key=str(i), org=slug, platform="greenhouse", slug=slug)
        for i, slug in enumerate(["good", "gone", "broken"], start=1)
    ]
    results = {r.board.slug: r for r in fetch_boards(boards, _client, workers=3)}
    assert results["good"].ok
    assert len(results["good"].postings) == 4
    assert not results["gone"].ok and "404" in (results["gone"].error or "")
    assert not results["broken"].ok
    assert results["broken"].postings == ()


def test_fetch_boards_with_no_boards() -> None:
    assert fetch_boards([], _client) == []


def test_scrape_due() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert scrape_due(None, 6, now)
    assert not scrape_due(now - timedelta(hours=5), 6, now)
    assert scrape_due(now - timedelta(hours=6), 6, now)
