"""Shared fixtures.

Unit tests never touch the network: pytest-socket blocks it (see pyproject),
and HTTP is faked with `responses`. Database tests need PostgreSQL at
TEST_DATABASE_URL (never DATABASE_URL: the fixtures drop every table). Each
test runs in a transaction that is rolled back, so tests never see each
other's rows. With REQUIRE_DATABASE set (CI), a missing database fails the run
instead of skipping.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from job_radar.app import create_app
from job_radar.config import Config
from job_radar.http import HostThrottle, HttpClient, RobotsCache
from job_radar.models import Base
from job_radar.sources.common import Board

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def make_board(platform: str, slug: str, **options: Any) -> Board:
    return Board(
        key="1", org="Example Org", platform=platform, slug=slug, category="Tech", options=options
    )


@pytest.fixture
def client_no_wait() -> HttpClient:
    """A polite client with its own robots cache and a throttle that doesn't sleep."""
    return HttpClient(
        contact_url="https://example.com/job-radar",
        robots=RobotsCache(),
        throttle=HostThrottle(interval=0),
        sleep=lambda _s: None,
    )


def _no_database(reason: str) -> None:
    """Skip database tests locally; fail when REQUIRE_DATABASE is set (CI), so
    a misconfigured run can't pass by skipping them."""
    if os.environ.get("REQUIRE_DATABASE"):
        pytest.fail(f"REQUIRE_DATABASE is set but {reason}")
    pytest.skip(reason)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    # Only TEST_DATABASE_URL, never DATABASE_URL: these tests drop every table.
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        _no_database("TEST_DATABASE_URL is not set")
        raise AssertionError("unreachable")
    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        _no_database(f"database unreachable: {exc}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as conn:
        outer = conn.begin()
        yield conn
        outer.rollback()


@pytest.fixture
def sessions(connection: Connection) -> sessionmaker[Session]:
    return sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
def session(sessions: sessionmaker[Session]) -> Iterator[Session]:
    s = sessions()
    yield s
    s.close()


@pytest.fixture
def app(engine: Engine, sessions: sessionmaker[Session]) -> Flask:
    config = Config(
        database_url="unused", contact_url="https://example.com/job-radar", testing=True
    )
    flask_app = create_app(config, engine=engine, sessions=sessions)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def api(app: Flask) -> FlaskClient:
    return app.test_client()
