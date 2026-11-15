"""GET /api/health: used by the compose healthcheck."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from job_radar import __version__
from job_radar.app import db

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health() -> Any:
    try:
        db().execute(text("SELECT 1"))
    except SQLAlchemyError:
        return jsonify(status="error", database="unreachable", version=__version__), 503
    return jsonify(status="ok", database="ok", version=__version__)
