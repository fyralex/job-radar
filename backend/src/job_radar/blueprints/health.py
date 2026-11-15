"""GET /api/health: used by the compose healthcheck.

503 when the database is down, or when Redis is configured but unreachable
(scraping can't take its locks then). `redis` is "not configured" without
REDIS_URL."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from job_radar import __version__
from job_radar.app import db, state

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health() -> Any:
    try:
        db().execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unreachable"
    app_state = state()
    if app_state.config.redis_url is None:
        redis_status = "not configured"
    else:
        redis_status = "ok" if app_state.locks.ping() else "unreachable"
    healthy = database == "ok" and redis_status != "unreachable"
    body = {
        "status": "ok" if healthy else "error",
        "database": database,
        "redis": redis_status,
        "version": __version__,
    }
    return jsonify(body), 200 if healthy else 503
