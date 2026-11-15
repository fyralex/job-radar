from __future__ import annotations

from collections.abc import Iterator

import pytest

from job_radar.coordination import (
    LOCAL_LOCKS,
    LocalLocks,
    Locks,
    RedisLocks,
    board_lock,
    holding,
    make_locks,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(params=["local", "redis"])
def locks(request: pytest.FixtureRequest) -> Iterator[Locks]:
    if request.param == "local":
        yield LocalLocks()
    else:
        request.applymarker(pytest.mark.redis)
        yield RedisLocks.from_url(request.getfixturevalue("redis_url"))


def test_one_holder_at_a_time(locks: Locks) -> None:
    token = locks.acquire("run", 60)
    assert token is not None
    assert locks.held("run")
    assert locks.acquire("run", 60) is None
    # Other names are independent.
    assert locks.acquire(board_lock("7"), 60) is not None


def test_only_the_holder_releases(locks: Locks) -> None:
    token = locks.acquire("run", 60)
    assert token is not None
    locks.release("run", "not-the-token")
    assert locks.held("run")
    locks.release("run", token)
    assert not locks.held("run")
    assert locks.acquire("run", 60) is not None


def test_holding_releases_on_exit_and_on_error(locks: Locks) -> None:
    with holding(locks, "run", 60) as got:
        assert got
        with holding(locks, "run", 60) as second:
            assert not second
        assert locks.held("run")  # the failed inner attempt released nothing
    assert not locks.held("run")
    with pytest.raises(RuntimeError), holding(locks, "run", 60):
        raise RuntimeError("boom")
    assert not locks.held("run")


def test_ping(locks: Locks) -> None:
    assert locks.ping()


def test_local_lock_expires() -> None:
    clock = FakeClock()
    locks = LocalLocks(clock=clock)
    old = locks.acquire("run", 10)
    assert old is not None
    clock.now += 11
    assert not locks.held("run")
    new = locks.acquire("run", 10)
    assert new is not None
    locks.release("run", old)  # the expired holder can't free the new one
    assert locks.held("run")


@pytest.mark.redis
def test_redis_lock_expires(redis_url: str) -> None:
    import time

    locks = RedisLocks.from_url(redis_url)
    old = locks.acquire("run", 0.05)
    assert old is not None
    time.sleep(0.15)
    assert not locks.held("run")
    assert locks.acquire("run", 60) is not None
    locks.release("run", old)
    assert locks.held("run")


@pytest.mark.redis
def test_redis_locks_are_shared_between_clients(redis_url: str) -> None:
    # Two clients stand in for the worker and the API process.
    worker, api = RedisLocks.from_url(redis_url), RedisLocks.from_url(redis_url)
    token = worker.acquire("run", 60)
    assert token is not None
    assert api.held("run")
    assert api.acquire("run", 60) is None
    worker.release("run", token)
    assert api.acquire("run", 60) is not None


def test_unreachable_redis_takes_no_lock() -> None:
    # Port 1 on localhost refuses connections.
    locks = RedisLocks.from_url("redis://127.0.0.1:1/0")
    assert locks.acquire("run", 60) is None
    assert not locks.held("run")
    assert not locks.ping()
    locks.release("run", "x")  # logs, doesn't raise


def test_make_locks() -> None:
    assert make_locks(None) is LOCAL_LOCKS
    assert isinstance(make_locks("redis://127.0.0.1:1/0"), RedisLocks)
