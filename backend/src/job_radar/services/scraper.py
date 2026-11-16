"""Fetch many boards in parallel.

Each board gets its own `HttpClient` (and so its own `requests.Session`) on a
pool of `workers` threads. Politeness is shared across threads: robots.txt is
cached per host and the per-host throttle spaces requests one second apart, so
two boards on the same API host still take turns. A board that fails is
reported with its error and never cached; the next run tries it again.

With `locks`, each board is fetched under its board lock. A board whose lock
is held elsewhere is skipped (`skipped=True`), not reported as failed.

With `cache`, every successful fetch is stored; with `use_cache` too, a
cached result is used instead of fetching (`cached=True`). See
`services/board_cache.py`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from job_radar.coordination import BOARD_LOCK_TTL_SECONDS, Locks, board_lock, holding
from job_radar.http import HttpClient
from job_radar.services.board_cache import BoardCache
from job_radar.sources import get_platform
from job_radar.sources.common import Board, BoardFetchError, RawPosting

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], HttpClient]


@dataclass(frozen=True)
class BoardResult:
    board: Board
    postings: tuple[RawPosting, ...]
    error: str | None
    seconds: float
    skipped: bool = False  # another process holds this board's lock
    cached: bool = False  # served from the board cache, not fetched

    @property
    def ok(self) -> bool:
        return self.error is None and not self.skipped


def fetch_one(board: Board, client_factory: ClientFactory) -> BoardResult:
    started = time.monotonic()
    client = client_factory()
    try:
        postings = get_platform(board.platform).fetch_board(client, board)
        return BoardResult(board, tuple(postings), None, time.monotonic() - started)
    except BoardFetchError as exc:
        error = str(exc)
    except Exception as exc:  # a parser bug must not take down the whole run
        logger.exception("unexpected error scraping %s", board.key)
        error = f"unexpected error: {type(exc).__name__}: {exc}"
    finally:
        client.close()
    return BoardResult(board, (), error, time.monotonic() - started)


def _fetch_locked(board: Board, client_factory: ClientFactory, locks: Locks) -> BoardResult:
    with holding(locks, board_lock(board.key), BOARD_LOCK_TTL_SECONDS) as got:
        if not got:
            return BoardResult(board, (), None, 0.0, skipped=True)
        return fetch_one(board, client_factory)


def fetch_boards(
    boards: Sequence[Board],
    client_factory: ClientFactory,
    workers: int = 8,
    locks: Locks | None = None,
    cache: BoardCache | None = None,
    *,
    use_cache: bool = False,
) -> list[BoardResult]:
    if not boards:
        return []

    def fetch(board: Board) -> BoardResult:
        if cache is not None and use_cache:
            hit = cache.get(board)
            if hit is not None:
                return BoardResult(board, hit, None, 0.0, cached=True)
        if locks is None:
            result = fetch_one(board, client_factory)
        else:
            result = _fetch_locked(board, client_factory, locks)
        if cache is not None and result.ok:  # failures are never cached
            cache.put(board, result.postings)
        return result

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(boards)))) as pool:
        return list(pool.map(fetch, boards))
