"""Shared fixtures.

Unit tests never touch the network: pytest-socket blocks it (see pyproject),
and HTTP is faked with `responses`. Database tests need PostgreSQL at
TEST_DATABASE_URL (or DATABASE_URL); each test runs in a transaction that is
rolled back, so tests never see each other's rows.
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


def _database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _database_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL / DATABASE_URL: database tests skipped")
    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        pytest.skip(f"database unreachable: {exc}")
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
