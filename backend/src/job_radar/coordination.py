"""Locks shared by every process that scrapes: the worker, the API's
"Refresh now" thread and `flask scrape`.

With `REDIS_URL` set, locks live in Redis, so they hold across containers.
Without it (a single process, local development) an in-process version keeps
the old behaviour.

- The **run lock** lets only one scrape run at a time.
- A **board lock** stops the same board being scraped twice at once.

Every lock has a TTL, so a process that dies mid-run can't block scraping for
good, and a random token, so only the holder can release it.

If Redis is unreachable, `acquire` returns None (no lock, so no scrape) and
`held` returns False, with a warning logged. The dashboard keeps working; it
just can't scrape until Redis is back. `/api/health` reports the outage.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Protocol

import redis

logger = logging.getLogger(__name__)

KEY_PREFIX = "job-radar:lock:"
RUN_LOCK = "run"
# Locks aren't renewed, so a TTL must outlast the work it guards. With the
# 1 request/second/host limit, a run takes about one second per request to its
# busiest host: 2h covers 7,200 requests to one host. One board's fetch waits
# behind at most the other scraper threads on its host (8 by default), so 15
# min covers a board of about 100 pages. Both only matter if a process dies.
RUN_LOCK_TTL_SECONDS = 2 * 3600
BOARD_LOCK_TTL_SECONDS = 15 * 60

# Delete the key only if it still holds our token, atomically.
_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def board_lock(board_key: str) -> str:
    return f"board:{board_key}"


class Locks(Protocol):
    def acquire(self, name: str, ttl_seconds: float) -> str | None:
        """Take the lock; return its token, or None if it is held elsewhere."""

    def release(self, name: str, token: str) -> None:
        """Release the lock if `token` still holds it."""

    def held(self, name: str) -> bool: ...

    def ping(self) -> bool:
        """True if the backing store is reachable."""


class LocalLocks:
    """In-process locks with the same contract, for runs without Redis."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._held: dict[str, tuple[str, float]] = {}
        self._mutex = threading.Lock()

    def _live(self, name: str) -> tuple[str, float] | None:
        entry = self._held.get(name)
        if entry is not None and entry[1] <= self._clock():
            del self._held[name]
            return None
        return entry

    def acquire(self, name: str, ttl_seconds: float) -> str | None:
        with self._mutex:
            if self._live(name) is not None:
                return None
            token = secrets.token_hex(16)
            self._held[name] = (token, self._clock() + ttl_seconds)
            return token

    def release(self, name: str, token: str) -> None:
        with self._mutex:
            entry = self._live(name)
            if entry is not None and entry[0] == token:
                del self._held[name]

    def held(self, name: str) -> bool:
        with self._mutex:
            return self._live(name) is not None

    def ping(self) -> bool:
        return True


class RedisLocks:
    """Locks in Redis: `SET key token NX PX ttl`, released by a compare-and-delete
    script so a lock that expired and was taken by someone else is left alone."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client
        self._release = client.register_script(_RELEASE)

    @classmethod
    def from_url(cls, url: str) -> RedisLocks:
        return cls(redis.Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5))

    def acquire(self, name: str, ttl_seconds: float) -> str | None:
        token = secrets.token_hex(16)
        try:
            ok = self._client.set(
                KEY_PREFIX + name, token, nx=True, px=max(1, int(ttl_seconds * 1000))
            )
        except redis.RedisError as exc:
            logger.warning("Redis unavailable; not taking lock %s: %s", name, exc)
            return None
        return token if ok else None

    def release(self, name: str, token: str) -> None:
        try:
            self._release(keys=[KEY_PREFIX + name], args=[token])
        except redis.RedisError as exc:
            # The TTL frees it in the end.
            logger.warning("Redis unavailable; lock %s not released: %s", name, exc)

    def held(self, name: str) -> bool:
        try:
            return bool(self._client.exists(KEY_PREFIX + name))
        except redis.RedisError as exc:
            logger.warning("Redis unavailable; can't check lock %s: %s", name, exc)
            return False

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False


# The default for one process without Redis, shared by its threads.
LOCAL_LOCKS = LocalLocks()


def make_locks(redis_url: str | None) -> Locks:
    return RedisLocks.from_url(redis_url) if redis_url else LOCAL_LOCKS


@contextmanager
def holding(locks: Locks, name: str, ttl_seconds: float) -> Iterator[bool]:
    """`with holding(locks, name, ttl) as got:` releases on exit if `got`."""
    token = locks.acquire(name, ttl_seconds)
    try:
        yield token is not None
    finally:
        if token is not None:
            locks.release(name, token)
