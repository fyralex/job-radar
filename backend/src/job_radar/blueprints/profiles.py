"""Job profiles: /api/profiles and /api/profiles/presets."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, jsonify
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from job_radar.app import db
from job_radar.blueprints._util import json_body
from job_radar.models import JobProfileRow
from job_radar.services.profiles_repo import (
    clean_profile_input,
    list_profiles,
    presets_json,
    profile_json,
)

bp = Blueprint("profiles", __name__, url_prefix="/api/profiles")


@bp.get("")
def get_profiles() -> Any:
    return jsonify([profile_json(p) for p in list_profiles(db())])


@bp.get("/presets")
def get_presets() -> Any:
    return jsonify(presets_json())


@bp.post("")
def create_profile() -> Any:
    session = db()
    clean = clean_profile_input(json_body())
    highest = session.scalar(select(func.max(JobProfileRow.position)))
    row = JobProfileRow(**clean, position=0 if highest is None else highest + 1)
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        abort(409, description="a profile with that name exists")
    return jsonify(profile_json(row)), 201


@bp.patch("/<int:profile_id>")
def update_profile(profile_id: int) -> Any:
    session = db()
    row = session.get(JobProfileRow, profile_id)
    if row is None:
        abort(404, description="no such profile")
    body = json_body()
    current = profile_json(row)
    clean = clean_profile_input({**current, **body})
    for name, value in clean.items():
        setattr(row, name, value)
    if "position" in body:
        if not isinstance(body["position"], int) or isinstance(body["position"], bool):
            raise ValueError("position must be a whole number")
        row.position = body["position"]
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        abort(409, description="a profile with that name exists")
    return jsonify(profile_json(row))


@bp.delete("/<int:profile_id>")
def delete_profile(profile_id: int) -> Any:
    session = db()
    row = session.get(JobProfileRow, profile_id)
    if row is None:
        abort(404, description="no such profile")
    session.delete(row)
    return "", 204
