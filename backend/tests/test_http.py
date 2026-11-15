"""The data collection policy, enforced by HttpClient."""

from __future__ import annotations

import pytest
import responses

from job_radar.http import HostThrottle, HttpClient, RobotsCache, user_agent
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
