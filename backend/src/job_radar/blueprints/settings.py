"""GET/PUT /api/settings."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify

from job_radar.app import db
from job_radar.blueprints._util import json_body
from job_radar.services.settings_repo import get_settings, settings_json, update_settings

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@bp.get("")
def read_settings() -> Any:
    return jsonify(settings_json(get_settings(db())))


@bp.put("")
def write_settings() -> Any:
    row = get_settings(db())
    update_settings(row, json_body())
    return jsonify(settings_json(row))
