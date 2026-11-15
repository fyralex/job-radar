"""The single settings row, and the rules built from it."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from job_radar.models import AppSettingsRow
from job_radar.services.location import LocationRule, parse_city
from job_radar.services.work_type import WORK_TYPES
from job_radar.sources.common import EMPLOYMENT_TYPES, STATE_CODES

# Reloading the page within this window doesn't count as a new visit, so the
# "New" badges survive a refresh.
VISIT_GAP = timedelta(minutes=30)


def get_settings(session: Session) -> AppSettingsRow:
    row = session.get(AppSettingsRow, 1)
    if row is None:
        row = AppSettingsRow(id=1)
        session.add(row)
        session.flush()
    return row


def location_rule(row: AppSettingsRow) -> LocationRule:
    return LocationRule.build(
        states=row.states,
        cities=row.cities,
        remote=row.remote,
        remote_states=row.remote_states,
        keep_unknown=row.keep_unknown_location,
    )


def settings_json(row: AppSettingsRow) -> dict[str, Any]:
    return {
        "max_age_days": row.max_age_days,
        "states": row.states,
        "cities": row.cities,
        "remote": row.remote,
        "remote_states": row.remote_states,
        "keep_unknown_location": row.keep_unknown_location,
        "employment_types": row.employment_types,
        "work_types": row.work_types,
        "scrape_interval_hours": row.scrape_interval_hours,
        "last_full_scrape_at": row.last_full_scrape_at.isoformat()
        if row.last_full_scrape_at
        else None,
    }


def _string_list(data: dict[str, Any], name: str) -> list[str]:
    value = data[name]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{name}' must be a list of strings")
    return [v.strip() for v in value if v.strip()]


def _int_in(data: dict[str, Any], name: str, low: int, high: int) -> int:
    value = data[name]
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"'{name}' must be a whole number from {low} to {high}")
    return value


def update_settings(row: AppSettingsRow, data: dict[str, Any]) -> None:
    """Apply a partial update. Raises ValueError on the first invalid field."""
    if "max_age_days" in data:
        row.max_age_days = _int_in(data, "max_age_days", 1, 365)
    if "scrape_interval_hours" in data:
        row.scrape_interval_hours = _int_in(data, "scrape_interval_hours", 1, 168)
    for name in ("states", "remote_states"):
        if name in data:
            codes = [s.upper() for s in _string_list(data, name)]
            bad = [c for c in codes if c not in STATE_CODES]
            if bad:
                raise ValueError(f"unknown state code(s): {', '.join(bad)}")
            setattr(row, name, sorted(set(codes)))
    if "cities" in data:
        cities = _string_list(data, "cities")
        bad = [c for c in cities if parse_city(c) is None]
        if bad:
            raise ValueError(f"cities must look like 'Austin, TX': {', '.join(bad)}")
        row.cities = cities
    for name, allowed in (("employment_types", EMPLOYMENT_TYPES), ("work_types", WORK_TYPES)):
        if name in data:
            values = _string_list(data, name)
            bad = [v for v in values if v not in allowed]
            if bad:
                raise ValueError(f"unknown {name}: {', '.join(bad)}")
            setattr(row, name, values)
    for name in ("remote", "keep_unknown_location"):
        if name in data:
            if not isinstance(data[name], bool):
                raise ValueError(f"'{name}' must be true or false")
            setattr(row, name, data[name])


def record_visit(row: AppSettingsRow, now: datetime) -> None:
    if row.last_visit_at is None or now - row.last_visit_at > VISIT_GAP:
        row.previous_visit_at = row.last_visit_at
    row.last_visit_at = now
