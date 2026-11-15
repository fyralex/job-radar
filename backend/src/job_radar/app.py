"""Flask application factory."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from flask import Flask, current_app, g, jsonify, request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.exceptions import HTTPException

from job_radar.config import Config
from job_radar.coordination import Locks, make_locks
from job_radar.db import make_engine, make_session_factory

EXTENSION = "job_radar"


@dataclass
class AppState:
    config: Config
    engine: Engine
    sessions: sessionmaker[Session]
    locks: Locks


def state() -> AppState:
    result: AppState = current_app.extensions[EXTENSION]
    return result


def db() -> Session:
    """The request's session, committed or rolled back when the request ends."""
    if "db" not in g:
        g.db = state().sessions()
    session: Session = g.db
    return session


def create_app(
    config: Config | None = None,
    engine: Engine | None = None,
    sessions: sessionmaker[Session] | None = None,
    locks: Locks | None = None,
) -> Flask:
    """`engine` and `sessions` let tests bind the app to a rolled-back
    transaction; `locks` lets them use a test Redis."""
    config = config or Config.from_env()
    app = Flask(__name__)
    app.json.sort_keys = False  # type: ignore[attr-defined]
    engine = engine or make_engine(config.database_url)
    app.extensions[EXTENSION] = AppState(
        config,
        engine,
        sessions or make_session_factory(engine),
        locks or make_locks(config.redis_url),
    )
    logging.basicConfig(level=logging.INFO)

    @app.teardown_appcontext
    def _close_session(exc: BaseException | None) -> None:
        session: Session | None = g.pop("db", None)
        if session is None:
            return
        try:
            if exc is None:
                session.commit()
            else:
                session.rollback()
        finally:
            session.close()

    @app.errorhandler(ValueError)
    def _bad_request(exc: ValueError) -> tuple[Any, int]:
        return jsonify(error=str(exc)), 400

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException) -> tuple[Any, int]:
        return jsonify(error=exc.description), exc.code or 500

    if config.cors_origins:

        @app.after_request
        def _cors(response: Any) -> Any:
            origin = request.headers.get("Origin")
            if origin in config.cors_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,PUT,DELETE"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response

    from job_radar.blueprints import (
        applications,
        boards,
        health,
        marks,
        postings,
        profiles,
        settings,
    )

    for module in (applications, boards, health, marks, postings, profiles, settings):
        app.register_blueprint(module.bp)

    from job_radar.cli import register_cli

    register_cli(app)
    return app
