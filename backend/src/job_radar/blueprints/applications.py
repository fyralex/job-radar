"""Applications: /api/applications and /api/applications/<id>/events."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, jsonify

from job_radar.app import db
from job_radar.blueprints._util import json_body, list_arg
from job_radar.models import ApplicationRow
from job_radar.services.applications_repo import (
    STATUSES,
    ApplicationExistsError,
    application_json,
    change_status,
    create_application,
    list_applications,
    update_application,
)

bp = Blueprint("applications", __name__, url_prefix="/api/applications")


def _get(application_id: int) -> ApplicationRow:
    row = db().get(ApplicationRow, application_id)
    if row is None:
        abort(404, description="no such application")
    return row


@bp.get("")
def get_applications() -> Any:
    rows = list_applications(db(), list_arg("status", STATUSES))
    return jsonify([application_json(r) for r in rows])


@bp.post("")
def post_application() -> Any:
    try:
        row = create_application(db(), json_body())
    except ApplicationExistsError:
        abort(409, description="that posting already has an application")
    return jsonify(application_json(row, with_events=True)), 201


@bp.get("/<int:application_id>")
def get_application(application_id: int) -> Any:
    return jsonify(application_json(_get(application_id), with_events=True))


@bp.patch("/<int:application_id>")
def patch_application(application_id: int) -> Any:
    row = update_application(_get(application_id), json_body())
    db().flush()
    return jsonify(application_json(row, with_events=True))


@bp.delete("/<int:application_id>")
def delete_application(application_id: int) -> Any:
    db().delete(_get(application_id))
    return "", 204


@bp.post("/<int:application_id>/events")
def post_event(application_id: int) -> Any:
    row = change_status(_get(application_id), json_body())
    db().flush()
    return jsonify(application_json(row, with_events=True)), 201
