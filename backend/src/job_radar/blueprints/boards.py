"""Boards the user follows: /api/boards, /api/boards/validate, /api/platforms."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, jsonify
from sqlalchemy.exc import IntegrityError

from job_radar.app import db, state
from job_radar.blueprints._util import json_body
from job_radar.http import HttpClient
from job_radar.models import BoardRow
from job_radar.services.boards_repo import board_json, clean_board_input, list_boards
from job_radar.services.runs_repo import recent_runs
from job_radar.services.scraper import fetch_one
from job_radar.sources import PLATFORMS
from job_radar.sources.common import Board

bp = Blueprint("boards", __name__, url_prefix="/api")


@bp.get("/platforms")
def platforms() -> Any:
    return jsonify(
        [
            {
                "id": key,
                "name": module.PLATFORM_NAME,
                "slug_help": module.SLUG_HELP,
                "options": {
                    name: {"kind": opt.kind, "help": opt.help}
                    for name, opt in module.OPTIONS.items()
                },
            }
            for key, module in PLATFORMS.items()
        ]
    )


@bp.get("/boards")
def get_boards() -> Any:
    session = db()
    runs = recent_runs(session)
    return jsonify([board_json(b, runs.get(b.id, ())) for b in list_boards(session)])


@bp.post("/boards/validate")
def validate_board() -> Any:
    """One test fetch, nothing stored: is the slug right and does it list jobs?"""
    data = clean_board_input(json_body())
    board = Board(
        key="validate",
        org=data["org"],
        platform=data["platform"],
        slug=data["slug"],
        category=data["category"],
        options=data["options"],
    )
    contact = state().config.contact_url
    result = fetch_one(board, lambda: HttpClient(contact))
    return jsonify(
        ok=result.ok,
        error=result.error,
        count=len(result.postings),
        sample=[p.title for p in result.postings[:5]],
    )


@bp.post("/boards")
def create_board() -> Any:
    session = db()
    row = BoardRow(**clean_board_input(json_body()))
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        abort(409, description="that board is already followed")
    return jsonify(board_json(row)), 201


@bp.patch("/boards/<int:board_id>")
def update_board(board_id: int) -> Any:
    session = db()
    row = session.get(BoardRow, board_id)
    if row is None:
        abort(404, description="no such board")
    current = {
        "platform": row.platform,
        "slug": row.slug,
        "org": row.org,
        "category": row.category,
        "options": row.options,
        "enabled": row.enabled,
    }
    clean = clean_board_input({**current, **json_body()})
    for name, value in clean.items():
        setattr(row, name, value)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        abort(409, description="that board is already followed")
    return jsonify(board_json(row, recent_runs(session, [row.id]).get(row.id, ())))


@bp.delete("/boards/<int:board_id>")
def delete_board(board_id: int) -> Any:
    session = db()
    row = session.get(BoardRow, board_id)
    if row is None:
        abort(404, description="no such board")
    session.delete(row)
    return "", 204
