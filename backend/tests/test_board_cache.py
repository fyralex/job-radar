from __future__ import annotations

import dataclasses

import pytest
import redis
import responses
from sqlalchemy.orm import Session, sessionmaker

from job_radar.http import HostThrottle, HttpClient, RobotsCache
from job_radar.models import BoardRow
from job_radar.services.board_cache import (
    RedisBoardCache,
    cache_key,
    make_board_cache,
)
from job_radar.services.refresh import run_scrape
from job_radar.services.scraper import fetch_boards
from job_radar.sources.common import Board, RawPosting
from tests.conftest import fixture_json

GREENHOUSE = "https://boards-api.greenhouse.io"
BOARD = Board(key="1", org="Acme", platform="greenhouse", slug="acme", category="Tech")
POSTING = RawPosting("1", "Acme", "Tech", "r1", "Engineer", "Remote - US", "", 3, "https://x/1")


def _client() -> HttpClient:
    return HttpClient(
        robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=lambda _s: None
    )


class MemoryCache:
    def __init__(self) -> None:
        self.entries: dict[str, tuple[RawPosting, ...]] = {}

    def get(self, board: Board) -> tuple[RawPosting, ...] | None:
        return self.entries.get(cache_key(board))

    def put(self, board: Board, postings: tuple[RawPosting, ...]) -> None:
        self.entries[cache_key(board)] = postings


def test_cache_key_follows_everything_that_shapes_the_result() -> None:
    assert cache_key(BOARD) == cache_key(dataclasses.replace(BOARD))
    for change in (
        {"slug": "other"},
        {"platform": "lever"},
        {"options": {"undated": True}},
        {"org": "Acme Inc"},
        {"category": "Ops"},
    ):
        assert cache_key(dataclasses.replace(BOARD, **change)) != cache_key(BOARD), change
    # Option order doesn't matter.
    a = dataclasses.replace(BOARD, options={"x": 1, "y": 2})
    b = dataclasses.replace(BOARD, options={"y": 2, "x": 1})
    assert cache_key(a) == cache_key(b)


def test_make_board_cache() -> None:
    assert make_board_cache(None, 3600) is None
    assert make_board_cache("redis://127.0.0.1:1/0", 0) is None
    assert isinstance(make_board_cache("redis://127.0.0.1:1/0", 3600), RedisBoardCache)


@pytest.mark.redis
def test_redis_cache_round_trip_with_ttl(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url)
    cache = RedisBoardCache(client, ttl_seconds=600)
    assert cache.get(BOARD) is None
    cache.put(BOARD, (POSTING,))
    assert cache.get(BOARD) == (POSTING,)
    assert 0 < client.ttl(cache_key(BOARD)) <= 600
    # An edited board misses.
    assert cache.get(dataclasses.replace(BOARD, slug="renamed")) is None


@pytest.mark.redis
def test_unreadable_entry_is_a_miss(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url)
    client.set(cache_key(BOARD), '[{"old_field": 1}]')
    assert RedisBoardCache(client).get(BOARD) is None


def test_redis_down_means_no_cache() -> None:
    cache = RedisBoardCache.from_url("redis://127.0.0.1:1/0")
    cache.put(BOARD, (POSTING,))  # logs, doesn't raise
    assert cache.get(BOARD) is None


@responses.activate
def test_fetch_boards_uses_and_fills_the_cache() -> None:
    responses.get(f"{GREENHOUSE}/robots.txt", status=404)
    jobs = responses.get(f"{GREENHOUSE}/v1/boards/acme/jobs", json=fixture_json("greenhouse.json"))
    cache = MemoryCache()

    # A refresh (use_cache=False) fetches and stores.
    [fresh] = fetch_boards([BOARD], _client, cache=cache)
    assert fresh.ok and not fresh.cached and jobs.call_count == 1
    assert cache.get(BOARD) == fresh.postings

    # A scheduled run (use_cache=True) reuses it without a request.
    [reused] = fetch_boards([BOARD], _client, cache=cache, use_cache=True)
    assert reused.cached and reused.ok and reused.postings == fresh.postings
    assert jobs.call_count == 1

    # A refresh ignores the cache and fetches again.
    fetch_boards([BOARD], _client, cache=cache)
    assert jobs.call_count == 2


@responses.activate
def test_failed_boards_are_never_cached() -> None:
    responses.get(f"{GREENHOUSE}/robots.txt", status=404)
    responses.get(f"{GREENHOUSE}/v1/boards/acme/jobs", status=404)
    cache = MemoryCache()
    [result] = fetch_boards([BOARD], _client, cache=cache, use_cache=True)
    assert not result.ok
    assert cache.entries == {}


@pytest.mark.redis
@pytest.mark.db
@responses.activate
def test_scheduled_run_after_a_refresh_reuses_the_cache(
    sessions: sessionmaker[Session], session: Session, redis_url: str
) -> None:
    row = BoardRow(platform="greenhouse", slug="acme", org="Acme", options={})
    session.add(row)
    session.commit()
    responses.get(f"{GREENHOUSE}/robots.txt", status=404)
    jobs = responses.get(f"{GREENHOUSE}/v1/boards/acme/jobs", json=fixture_json("greenhouse.json"))
    cache = RedisBoardCache.from_url(redis_url)

    refresh = run_scrape(sessions, None, client_factory=_client, cache=cache)
    assert refresh is not None and refresh.cached == 0 and jobs.call_count == 1

    scheduled = run_scrape(sessions, None, client_factory=_client, cache=cache, use_cache=True)
    assert scheduled is not None
    assert (scheduled.boards, scheduled.cached, scheduled.postings) == (1, 1, 4)
    assert jobs.call_count == 1  # nothing fetched
    session.expire_all()
    stored = session.get(BoardRow, row.id)
    assert stored is not None and stored.last_status == "ok" and stored.last_count == 4
