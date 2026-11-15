"""Fetch many boards in parallel.

Each board gets its own `HttpClient` (and so its own `requests.Session`) on a
pool of `workers` threads. Politeness is shared across threads: robots.txt is
cached per host and the per-host throttle spaces requests one second apart, so
two boards on the same API host still take turns. A board that fails is
reported with its error and never cached; the next run tries it again.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from job_radar.http import HttpClient
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

    @property
    def ok(self) -> bool:
        return self.error is None


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


def fetch_boards(
    boards: Sequence[Board], client_factory: ClientFactory, workers: int = 8
) -> list[BoardResult]:
    if not boards:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(boards)))) as pool:
        return list(pool.map(lambda b: fetch_one(b, client_factory), boards))
