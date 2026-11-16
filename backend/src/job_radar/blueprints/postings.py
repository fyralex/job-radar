"""GET /api/postings, POST /api/refresh, POST /api/visits."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, jsonify

from job_radar.app import db, state
from job_radar.blueprints._util import bool_arg, int_arg, list_arg
from job_radar.models import JobProfileRow, utcnow
from job_radar.services.applications_repo import applied_posting_keys
from job_radar.services.boards_repo import list_boards
from job_radar.services.filters import PostingView, ViewFilters, apply_filters
from job_radar.services.marks_repo import hidden_keys
from job_radar.services.postings_repo import open_postings
from job_radar.services.profiles_repo import matcher_for
from job_radar.services.refresh import is_running, start_in_background
from job_radar.services.settings_repo import get_settings, location_rule, record_visit
from job_radar.services.work_type import WORK_TYPES
from job_radar.sources.common import EMPLOYMENT_TYPES

bp = Blueprint("postings", __name__, url_prefix="/api")


def posting_json(p: PostingView) -> dict[str, Any]:
    return {
        "id": p.id,
        "posting_key": p.posting_key,
        "board_id": p.board_id,
        "org": p.org,
        "category": p.category,
        "title": p.title,
        "location": p.location,
        "url": p.url,
        "posted_on": p.posted_on.isoformat() if p.posted_on else None,
        "posted_age_days": p.posted_age_days,
        "work_type": p.work_type,
        "employment_type": p.employment_type,
        "first_seen_at": p.first_seen_at.isoformat(),
        "is_new": p.is_new,
        "local": p.local,
    }


@bp.get("/postings")
def get_postings() -> Any:
    """Open postings after the user's filters. Query params override the saved
    settings for this request only: maxAgeDays, employmentType, workType,
    category (repeatable), local=true, profile=<id> (omit for every posting).
    Marked postings and postings with an application are left out."""
    session = db()
    settings = get_settings(session)
    rule = location_rule(settings)
    now = utcnow()

    matcher = None
    profile_id = int_arg("profile", 1, 2**31 - 1)
    if profile_id is not None:
        profile = session.get(JobProfileRow, profile_id)
        if profile is None:
            abort(404, description="no such profile")
        matcher = matcher_for(profile)

    max_age = int_arg("maxAgeDays", 1, 365)
    employment = list_arg("employmentType", EMPLOYMENT_TYPES) or settings.employment_types
    work_types = list_arg("workType", WORK_TYPES) or settings.work_types
    filters = ViewFilters(
        rule=rule,
        max_age_days=max_age if max_age is not None else settings.max_age_days,
        employment_types=employment,
        work_types=work_types,
        categories=list_arg("category"),
        local_only=bool_arg("local"),
        # Hidden or not-interested marks, and postings already in Applications.
        hidden_keys=hidden_keys(session) | applied_posting_keys(session),
        matcher=matcher,
    )
    views = apply_filters(
        open_postings(session, rule, now.date(), settings.previous_visit_at), filters
    )
    views.sort(key=lambda p: (not p.is_new, p.posted_age_days is None, p.posted_age_days or 0))
    failures = [
        {"board_id": b.id, "org": b.org, "error": b.last_error}
        for b in list_boards(session)
        if b.enabled and b.last_status == "error"
    ]
    return jsonify(
        postings=[posting_json(p) for p in views],
        failures=failures,
        scraped_at=settings.last_full_scrape_at.isoformat()
        if settings.last_full_scrape_at
        else None,
        refreshing=is_running(state().locks),
    )


@bp.post("/refresh")
def refresh() -> Any:
    """Start a scrape in the background: 202 with `started: true`. Otherwise
    200 with `started: false` and a `reason`: "already_running" (another run
    holds the lock) or "unavailable" (the lock can't be taken, e.g. Redis is
    down)."""
    app_state = state()
    started = start_in_background(
        app_state.sessions,
        app_state.config.contact_url,
        app_state.config.scrape_workers,
        locks=app_state.locks,
    )
    if started:
        return jsonify(started=True, refreshing=True, reason=None), 202
    running = is_running(app_state.locks)
    reason = "already_running" if running else "unavailable"
    return jsonify(started=False, refreshing=running, reason=reason), 200


@bp.post("/visits")
def visit() -> Any:
    """Called once per dashboard load: moves the "new since" marker."""
    settings = get_settings(db())
    record_visit(settings, utcnow())
    since = settings.previous_visit_at
    return jsonify(new_since=since.isoformat() if since else None)
