"""Hidden postings: GET/POST /api/marks, DELETE /api/marks?key=<posting_key>."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, jsonify, request

from job_radar.app import db
from job_radar.blueprints._util import json_body
from job_radar.services.marks_repo import add_mark, list_marks, mark_json, remove_mark

bp = Blueprint("marks", __name__, url_prefix="/api/marks")


@bp.get("")
def get_marks() -> Any:
    return jsonify([mark_json(m) for m in list_marks(db())])


@bp.post("")
def post_mark() -> Any:
    return jsonify(mark_json(add_mark(db(), json_body()))), 201


@bp.delete("")
def delete_mark() -> Any:
    key = request.args.get("key", "")
    if not key:
        abort(400, description="key is required")
    if not remove_mark(db(), key):
        abort(404, description="no such mark")
    return "", 204
