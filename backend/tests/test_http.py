"""The data collection policy, enforced by HttpClient."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest
import redis
import requests
import responses

from job_radar.http import (
    THROTTLE,
    THROTTLE_KEY_PREFIX,
    HostThrottle,
    HttpClient,
    RedisThrottle,
    RobotsCache,
    configure_throttle,
    default_throttle,
    user_agent,
)
from job_radar.sources.common import BoardFetchError

URL = "https://api.example.com/v1/jobs"
ROBOTS = "https://api.example.com/robots.txt"


def test_user_agent_is_honest() -> None:
    assert user_agent(None).startswith("job-radar/")
    assert user_agent("https://example.com/repo").endswith("(+https://example.com/repo)")
    assert "Mozilla" not in user_agent("https://example.com/repo")


@responses.activate
def test_allowed_path(client_no_wait: HttpClient) -> None:
    responses.get(ROBOTS, body="User-agent: *\nDisallow: /private\n")
    responses.get(URL, json={"ok": True})
    assert client_no_wait.get_json(URL) == {"ok": True}


@responses.activate
def test_disallowed_path_is_never_requested(client_no_wait: HttpClient) -> None:
    responses.get(ROBOTS, body="User-agent: *\nDisallow: /\n")
    job_call = responses.get(URL, json={})
    with pytest.raises(BoardFetchError, match=r"robots\.txt disallows"):
        client_no_wait.get(URL)
    assert job_call.call_count == 0


@responses.activate
@pytest.mark.parametrize("status", [401, 403, 404])
def test_robots_4xx_means_allow_all(client_no_wait: HttpClient, status: int) -> None:
    """RFC 9309: a 4xx robots.txt is 'unavailable', so access is allowed."""
    responses.get(ROBOTS, status=status)
    responses.get(URL, json={"ok": True})
    assert client_no_wait.get_json(URL) == {"ok": True}


@responses.activate
def test_robots_5xx_means_disallow(client_no_wait: HttpClient) -> None:
    responses.get(ROBOTS, status=503)
    with pytest.raises(BoardFetchError, match=r"robots\.txt"):
        client_no_wait.get(URL)


@responses.activate
def test_robots_is_cached_per_host(client_no_wait: HttpClient) -> None:
    robots = responses.get(ROBOTS, body="User-agent: *\nAllow: /\n")
    responses.get(URL, json={})
    client_no_wait.get(URL)
    client_no_wait.get(URL)
    assert robots.call_count == 1


@responses.activate
def test_retries_429_honouring_retry_after() -> None:
    waits: list[float] = []
    client = HttpClient(robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=waits.append)
    responses.get(ROBOTS, status=404)
    responses.get(URL, status=429, headers={"Retry-After": "7"})
    responses.get(URL, json={"ok": True})
    assert client.get_json(URL) == {"ok": True}
    assert waits == [7.0]


@responses.activate
def test_gives_up_after_retries() -> None:
    client = HttpClient(
        robots=RobotsCache(), throttle=HostThrottle(interval=0), sleep=lambda _s: None
    )
    responses.get(ROBOTS, status=404)
    responses.get(URL, status=503)
    with pytest.raises(BoardFetchError, match="HTTP 503"):
        client.get(URL)


@responses.activate
def test_404_is_not_retried(client_no_wait: HttpClient) -> None:
    responses.get(ROBOTS, status=404)
    call = responses.get(URL, status=404)
    with pytest.raises(BoardFetchError, match="HTTP 404"):
        client_no_wait.get(URL)
    assert call.call_count == 1


def test_throttle_spaces_requests_per_host() -> None:
    now = [100.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)

    throttle = HostThrottle(interval=1.0, clock=lambda: now[0], sleep=sleep)
    throttle.wait("a.example.com")
    throttle.wait("a.example.com")
    throttle.wait("b.example.com")
    throttle.wait("a.example.com")
    assert slept == [1.0, 2.0]


class RecordingThrottle:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    def wait(self, host: str) -> None:
        self.hosts.append(host)


@pytest.mark.redis
def test_redis_throttle_spaces_requests_per_host(redis_url: str) -> None:
    slept: list[float] = []
    throttle = RedisThrottle(
        redis.Redis.from_url(redis_url), interval=1.0, sleep=slept.append, local=RecordingThrottle()
    )
    throttle.wait("a.example.com")  # first request: no wait
    throttle.wait("a.example.com")  # one slot later
    throttle.wait("b.example.com")  # another host: no wait
    throttle.wait("a.example.com")  # two slots later
    assert len(slept) == 2
    assert 0.9 < slept[0] <= 1.0
    assert 1.9 < slept[1] <= 2.0


@pytest.mark.redis
def test_redis_throttle_is_shared_between_processes(redis_url: str) -> None:
    # Two clients stand in for the worker and the API process.
    worker_waits: list[float] = []
    api_waits: list[float] = []
    worker = RedisThrottle(redis.Redis.from_url(redis_url), sleep=worker_waits.append)
    api = RedisThrottle(redis.Redis.from_url(redis_url), sleep=api_waits.append)
    worker.wait("a.example.com")
    api.wait("a.example.com")
    assert worker_waits == []
    assert len(api_waits) == 1 and 0.9 < api_waits[0] <= 1.0


@pytest.mark.redis
def test_redis_throttle_frees_the_slot_after_the_interval(redis_url: str) -> None:
    slept: list[float] = []
    throttle = RedisThrottle(redis.Redis.from_url(redis_url), interval=0.05, sleep=slept.append)
    throttle.wait("a.example.com")
    time.sleep(0.08)
    throttle.wait("a.example.com")
    assert slept == []
    # The key expires on its own, so idle hosts leave nothing behind.
    ttl = redis.Redis.from_url(redis_url).pttl(THROTTLE_KEY_PREFIX + "a.example.com")
    assert 0 < ttl <= 1100


def test_redis_throttle_still_throttles_locally_when_redis_is_down() -> None:
    local = RecordingThrottle()
    slept: list[float] = []
    throttle = RedisThrottle(
        redis.Redis.from_url("redis://127.0.0.1:1/0"), sleep=slept.append, local=local
    )
    throttle.wait("a.example.com")
    assert local.hosts == ["a.example.com"]
    assert slept == []


@pytest.mark.redis
def test_redis_throttle_keeps_spacing_when_redis_flaps(redis_url: str) -> None:
    # Redis works, fails, then comes back empty (a restart): each request to
    # the host must still wait its turn, through the local throttle.
    local_slept: list[float] = []
    local = HostThrottle(interval=1.0, clock=lambda: 0.0, sleep=local_slept.append)
    client = redis.Redis.from_url(redis_url)
    throttle = RedisThrottle(client, sleep=lambda _s: None, local=local)
    working = throttle._reserve

    def failing(**_kwargs: object) -> int:
        raise redis.ConnectionError("Redis went away")

    throttle.wait("a.example.com")  # Redis up
    throttle._reserve = failing  # type: ignore[assignment]
    throttle.wait("a.example.com")  # Redis down
    throttle._reserve = working
    client.flushdb()  # Redis back, with no memory of the host
    throttle.wait("a.example.com")
    assert local_slept == [1.0, 2.0]


@pytest.fixture
def restore_default_throttle() -> Iterator[None]:
    yield
    configure_throttle(None)


@pytest.mark.usefixtures("restore_default_throttle")
def test_configure_throttle_sets_the_default_for_new_clients() -> None:
    assert default_throttle() is THROTTLE
    assert HttpClient()._throttle is THROTTLE
    shared = configure_throttle("redis://127.0.0.1:1/0")
    assert isinstance(shared, RedisThrottle)
    assert HttpClient()._throttle is shared
    assert configure_throttle(None) is THROTTLE


@pytest.mark.redis
def test_redis_throttle_gives_concurrent_callers_distinct_slots(redis_url: str) -> None:
    # Eight threads across two "processes" ask for the same host at once.
    waits: list[float] = []
    lock = threading.Lock()

    def record(seconds: float) -> None:
        with lock:
            waits.append(seconds)

    # No local throttle here: this checks the Redis side alone.
    throttles = [
        RedisThrottle(redis.Redis.from_url(redis_url), sleep=record, local=RecordingThrottle())
        for _ in range(2)
    ]
    threads = [
        threading.Thread(target=throttles[i % 2].wait, args=("a.example.com",)) for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # One caller went straight away; the others got one slot each, 1s apart.
    slots = sorted(round(w) for w in waits)
    assert slots == [1, 2, 3, 4, 5, 6, 7]


class EventThrottle:
    """Records each wait into a shared event log, next to the requests sent."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def wait(self, host: str) -> None:
        self.events.append(f"wait {host}")


@responses.activate
def test_robots_fetch_takes_its_own_throttle_slot() -> None:
    events: list[str] = []

    def record(request: requests.PreparedRequest) -> tuple[int, dict[str, str], str]:
        events.append(f"GET {request.url}")
        return (200, {}, "{}" if request.url == URL else "")

    responses.add_callback(responses.GET, ROBOTS, callback=record)
    responses.add_callback(responses.GET, URL, callback=record)
    client = HttpClient(robots=RobotsCache(), throttle=EventThrottle(events), sleep=lambda _s: None)
    client.get(URL)
    # Cold cache: robots.txt waits for a slot, then the request waits for the next.
    assert events == [
        "wait api.example.com",
        f"GET {ROBOTS}",
        "wait api.example.com",
        f"GET {URL}",
    ]
    events.clear()
    client.get(URL)
    # Warm cache: one slot, one request.
    assert events == ["wait api.example.com", f"GET {URL}"]


@responses.activate
def test_retries_each_take_a_throttle_slot() -> None:
    events: list[str] = []
    responses.get(ROBOTS, status=404)
    responses.get(URL, status=503)
    responses.get(URL, json={"ok": True})
    client = HttpClient(robots=RobotsCache(), throttle=EventThrottle(events), sleep=lambda _s: None)
    assert client.get_json(URL) == {"ok": True}
    # robots.txt, the 503, and the retry: three slots for three requests.
    assert events == ["wait api.example.com"] * 3


@responses.activate
def test_cached_disallow_sends_nothing_and_waits_for_nothing() -> None:
    events: list[str] = []
    responses.get(ROBOTS, body="User-agent: *\nDisallow: /\n")
    client = HttpClient(robots=RobotsCache(), throttle=EventThrottle(events), sleep=lambda _s: None)
    with pytest.raises(BoardFetchError):
        client.get(URL)
    assert events == ["wait api.example.com"]  # only for robots.txt itself
    with pytest.raises(BoardFetchError):
        client.get(URL)
    assert events == ["wait api.example.com"]
