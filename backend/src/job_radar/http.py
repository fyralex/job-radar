"""The one HTTP client every source module uses. It enforces the data
collection policy in CLAUDE.md on every request:

- An honest User-Agent naming this app and, if `CONTACT_URL` is set, where to
  find it. Never a browser string.
- robots.txt is checked before every request, cached per host for 24 hours.
  Fetching robots.txt counts as a request: it waits on the throttle too.
  Fetch rules follow RFC 9309: a 2xx file is parsed with `urllib.robotparser`,
  any 4xx means there are no rules (allow all), and a 5xx or a network error
  means "unreachable", so the whole host is treated as disallowed until the
  next check. (Python's own `RobotFileParser.read()` treats 401/403 as
  disallow-all, which the RFC doesn't; one public posting API answers its
  robots.txt with 401.)
- At most one request per second per host. With `REDIS_URL` the limit is
  shared by every process (`RedisThrottle`); without it, by every thread in
  the process (`HostThrottle`).
- 429 and 5xx responses are retried with backoff, honouring `Retry-After`.
- Redirects are followed by hand (never by `requests`), up to
  `MAX_REDIRECTS`: every hop takes a throttle slot for its own host, and a
  request's every hop is checked against that host's robots.txt first.

A disallowed path or a blocked request raises `BoardFetchError`; the board is
then reported as failed. Never work around a block.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import redis
import requests

from job_radar import __version__
from job_radar.errors import BoardFetchError

logger = logging.getLogger(__name__)

ROBOTS_TTL_SECONDS = 24 * 3600
MIN_INTERVAL_SECONDS = 1.0
MAX_RETRIES = 3
MAX_RETRY_AFTER_SECONDS = 60.0
DEFAULT_TIMEOUT = 30.0
# RFC 9309 asks crawlers to follow at least five redirects for robots.txt;
# the same limit applies to ordinary requests.
MAX_REDIRECTS = 5


def user_agent(contact_url: str | None) -> str:
    base = f"job-radar/{__version__}"
    return f"{base} (+{contact_url})" if contact_url else base


@dataclass
class _Robots:
    parser: urllib.robotparser.RobotFileParser | None  # None = allow all
    disallow_all: bool
    fetched_at: float


class RobotsCache:
    """robots.txt per scheme+host, shared by every client in the process."""

    def __init__(self, ttl: float = ROBOTS_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._entries: dict[str, _Robots] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def allowed(
        self,
        session: requests.Session,
        url: str,
        agent: str,
        throttle: Throttle,
    ) -> bool:
        """Whether robots.txt lets `agent` fetch `url`. A robots.txt fetch
        (cold or stale cache) waits on `throttle` for each hop, like any
        request; `throttle` is required so no caller can skip that."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            entry = self._entries.get(origin)
        if entry is None or time.monotonic() - entry.fetched_at > self._ttl:
            entry = self._fetch(session, origin, agent, throttle)
            with self._lock:
                self._entries[origin] = entry
        if entry.disallow_all:
            return False
        if entry.parser is None:
            return True
        return entry.parser.can_fetch(agent, url)

    @staticmethod
    def _fetch(session: requests.Session, origin: str, agent: str, throttle: Throttle) -> _Robots:
        now = time.monotonic()
        url = f"{origin}/robots.txt"
        try:
            for _hop in range(MAX_REDIRECTS + 1):
                throttle.wait(urlsplit(url).netloc)
                response = session.get(
                    url,
                    headers={"User-Agent": agent},
                    timeout=DEFAULT_TIMEOUT,
                    allow_redirects=False,
                )
                if not response.is_redirect:
                    break
                url = urljoin(url, response.headers["Location"])
            else:
                # More redirects than RFC 9309 asks us to follow. The RFC lets
                # a crawler treat that as "unavailable" (allow all); we take
                # the cautious reading and stay off the host until the next check.
                logger.warning("robots.txt for %s redirects too often", origin)
                return _Robots(None, True, now)
        except requests.RequestException as exc:
            logger.warning("robots.txt unreachable for %s: %s", origin, exc)
            return _Robots(None, True, now)
        if 400 <= response.status_code < 500:
            return _Robots(None, False, now)
        if response.status_code >= 500:
            return _Robots(None, True, now)
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        return _Robots(parser, False, now)


class Throttle(Protocol):
    def wait(self, host: str) -> None:
        """Block until this process may send the next request to `host`."""


class HostThrottle:
    """At most one request per `interval` seconds per host, across threads."""

    def __init__(
        self,
        interval: float = MIN_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._next_slot: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot.get(host, now))
            self._next_slot[host] = slot + self._interval
        if slot > now:
            self._sleep(slot - now)


THROTTLE_KEY_PREFIX = "job-radar:throttle:"

# Reserve the host's next slot atomically, on Redis's clock so every process
# agrees on the time. Returns how long the caller must wait, in microseconds.
_RESERVE_SLOT = """
local t = redis.call("TIME")
local now = tonumber(t[1]) * 1000000 + tonumber(t[2])
local slot = math.max(now, tonumber(redis.call("GET", KEYS[1]) or "0"))
local next_slot = slot + tonumber(ARGV[1])
local ttl_ms = math.ceil((next_slot - now) / 1000) + 1000
redis.call("SET", KEYS[1], string.format("%d", next_slot), "PX", ttl_ms)
return slot - now
"""


class RedisThrottle:
    """The per-host limit shared by every process through Redis.

    Every call first waits on `local`, an in-process throttle, then reserves
    the host's next free slot in Redis (`interval` apart) and sleeps until it.
    The local throttle always runs, so requests from this process stay spaced
    even when Redis fails, comes back empty, or flaps between the two; Redis
    adds the spacing against other processes."""

    def __init__(
        self,
        client: redis.Redis,
        interval: float = MIN_INTERVAL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        local: Throttle | None = None,
    ) -> None:
        self._reserve = client.register_script(_RESERVE_SLOT)
        self._interval_us = int(interval * 1_000_000)
        self._sleep = sleep
        self._local = local if local is not None else HostThrottle(interval)

    @classmethod
    def from_url(cls, url: str) -> RedisThrottle:
        return cls(redis.Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5))

    def wait(self, host: str) -> None:
        self._local.wait(host)
        try:
            wait_us = int(
                self._reserve(keys=[THROTTLE_KEY_PREFIX + host], args=[self._interval_us])
            )
        except redis.RedisError as exc:
            logger.warning("Redis unavailable; throttling %s in this process only: %s", host, exc)
            return
        if wait_us > 0:
            self._sleep(wait_us / 1_000_000)


ROBOTS = RobotsCache()
THROTTLE = HostThrottle()
_default_throttle: Throttle = THROTTLE


def configure_throttle(redis_url: str | None) -> Throttle:
    """Choose the throttle new clients use by default: shared through Redis
    when `redis_url` is set, else in-process. Called once at process start by
    the entry points (wsgi, worker), not by `create_app`, so tests stay
    isolated."""
    global _default_throttle  # noqa: PLW0603 - one setting per process, set at start
    _default_throttle = RedisThrottle.from_url(redis_url) if redis_url else THROTTLE
    return _default_throttle


def default_throttle() -> Throttle:
    return _default_throttle


def _retry_after(response: requests.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            try:
                when = parsedate_to_datetime(header).timestamp()
                return min(max(when - time.time(), 0.0), MAX_RETRY_AFTER_SECONDS)
            except (TypeError, ValueError):
                pass
    return float(2**attempt)


class HttpClient:
    """A polite wrapper around one `requests.Session`. Not shared between
    threads: the scraper makes one per board."""

    def __init__(
        self,
        contact_url: str | None = None,
        session: requests.Session | None = None,
        robots: RobotsCache = ROBOTS,
        throttle: Throttle | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.agent = user_agent(contact_url)
        self.session.headers["User-Agent"] = self.agent
        self._robots = robots
        self._throttle = throttle if throttle is not None else default_throttle()
        self._sleep = sleep

    def close(self) -> None:
        self.session.close()

    def get(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> requests.Response:
        """GET with robots, throttle, retries and redirects. Raises
        BoardFetchError for a disallowed path (on any hop), a final non-2xx
        status, too many redirects or a network error."""
        for _hop in range(MAX_REDIRECTS + 1):
            response = self._get_once(url, params, headers, timeout)
            if not response.is_redirect:
                return response
            # The target is a new request: robots check and slot on its own host.
            url = urljoin(response.url, response.headers["Location"])
            params = None  # already part of the URL that redirected
        raise BoardFetchError(f"{urlsplit(url).netloc}: more than {MAX_REDIRECTS} redirects")

    def _get_once(
        self,
        url: str,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str] | None,
        timeout: float,
    ) -> requests.Response:
        """One hop: robots check, then the request with its retries, never
        following a redirect."""
        host = urlsplit(url).netloc
        # robots.txt first: fetching it (if not cached) takes its own throttle
        # slot, so it is never sent back to back with the request below.
        if not self._robots.allowed(self.session, url, self.agent, self._throttle):
            raise BoardFetchError(f"robots.txt disallows {url}")
        for attempt in range(MAX_RETRIES + 1):
            self._throttle.wait(host)
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=dict(headers or {}),
                    timeout=timeout,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise BoardFetchError(f"{host}: {exc}") from exc
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < MAX_RETRIES:
                self._sleep(_retry_after(response, attempt))
                continue
            if response.status_code >= 400:
                raise BoardFetchError(f"{host}: HTTP {response.status_code} for {response.url}")
            return response
        raise BoardFetchError(f"{host}: gave up after {MAX_RETRIES} retries")  # pragma: no cover

    def get_json(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> object:
        response = self.get(
            url, params=params, headers={"Accept": "application/json"}, timeout=timeout
        )
        try:
            return response.json()
        except ValueError as exc:
            raise BoardFetchError(f"{urlsplit(url).netloc}: response is not JSON") from exc
