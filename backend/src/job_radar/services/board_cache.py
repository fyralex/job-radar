"""Per-board result cache in Redis.

A successful fetch is stored for `CACHE_TTL_SECONDS` (3h by default), so a
scheduled run shortly after a "Refresh now" reuses it instead of asking the
employer's board again. Failed fetches are never stored.

- Scheduled runs read the cache. "Refresh now" and `flask scrape` skip the
  read but store what they fetch, so the cache stays fresh.
- The key includes a fingerprint of everything that shapes the result
  (platform, slug, options, org, category), so editing a board never serves
  its old postings.
- Postings carry `posted_age_days` from fetch time, so a cached posting's age
  can be up to one TTL behind. That is within the dashboard's day-level ages.
- Without Redis there is no cache; if Redis errors, a read is a miss and a
  write is dropped, with a warning.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from typing import Protocol

import redis

from job_radar.sources.common import Board, RawPosting

logger = logging.getLogger(__name__)

KEY_PREFIX = "job-radar:cache:board:"
DEFAULT_TTL_SECONDS = 3 * 3600


def cache_key(board: Board) -> str:
    shape = json.dumps(
        [board.platform, board.slug, dict(board.options), board.org, board.category],
        sort_keys=True,
        default=str,
    )
    fingerprint = hashlib.sha256(shape.encode()).hexdigest()[:16]
    return f"{KEY_PREFIX}{board.key}:{fingerprint}"


class BoardCache(Protocol):
    def get(self, board: Board) -> tuple[RawPosting, ...] | None:
        """The cached postings, or None on a miss."""

    def put(self, board: Board, postings: tuple[RawPosting, ...]) -> None: ...


class RedisBoardCache:
    def __init__(self, client: redis.Redis, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> RedisBoardCache:
        client = redis.Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5)
        return cls(client, ttl_seconds)

    def get(self, board: Board) -> tuple[RawPosting, ...] | None:
        try:
            raw = self._client.get(cache_key(board))
        except redis.RedisError as exc:
            logger.warning(
                "Redis unavailable; not using the cache for board %s: %s", board.key, exc
            )
            return None
        if raw is None:
            return None
        try:
            return tuple(RawPosting(**item) for item in json.loads(raw))
        except (ValueError, TypeError) as exc:
            # Written by an older version with a different shape: just refetch.
            logger.warning("ignoring unreadable cache entry for board %s: %s", board.key, exc)
            return None

    def put(self, board: Board, postings: tuple[RawPosting, ...]) -> None:
        body = json.dumps([dataclasses.asdict(p) for p in postings])
        try:
            self._client.set(cache_key(board), body, ex=self._ttl)
        except redis.RedisError as exc:
            logger.warning("Redis unavailable; board %s not cached: %s", board.key, exc)


def make_board_cache(redis_url: str | None, ttl_seconds: int) -> BoardCache | None:
    if not redis_url or ttl_seconds <= 0:
        return None
    return RedisBoardCache.from_url(redis_url, ttl_seconds)
