"""Job profiles: validation, JSON shape and matchers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_radar.models import JobProfileRow
from job_radar.services.matching import PRESETS, Preset, ProfileMatcher

MAX_TERMS = 200


def _terms(data: dict[str, Any], name: str) -> list[str]:
    value = data.get(name, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{name}' must be a list of strings")
    terms = [v.strip() for v in value if v.strip()]
    if len(terms) > MAX_TERMS:
        raise ValueError(f"'{name}' has more than {MAX_TERMS} terms")
    return terms


def clean_profile_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a create/update body, including that every term compiles."""
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 100:
        raise ValueError("name is required (at most 100 characters)")
    include = _terms(data, "include_terms")
    exclude = _terms(data, "exclude_terms")
    seniority = _terms(data, "seniority_terms")
    advanced = bool(data.get("advanced", False))
    if not include:
        raise ValueError("add at least one include term")
    ProfileMatcher.build(include, exclude, seniority, advanced)  # raises on a bad pattern
    return {
        "name": name,
        "include_terms": include,
        "exclude_terms": exclude,
        "seniority_terms": seniority,
        "advanced": advanced,
        "enabled": bool(data.get("enabled", True)),
    }


def matcher_for(row: JobProfileRow) -> ProfileMatcher:
    return ProfileMatcher.build(
        row.include_terms, row.exclude_terms, row.seniority_terms, row.advanced
    )


def list_profiles(session: Session) -> list[JobProfileRow]:
    return list(
        session.scalars(select(JobProfileRow).order_by(JobProfileRow.position, JobProfileRow.id))
    )


def profile_json(row: JobProfileRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "include_terms": row.include_terms,
        "exclude_terms": row.exclude_terms,
        "seniority_terms": row.seniority_terms,
        "advanced": row.advanced,
        "position": row.position,
        "enabled": row.enabled,
    }


def preset_json(preset: Preset) -> dict[str, Any]:
    return {
        "key": preset.key,
        "name": preset.name,
        "description": preset.description,
        "include_terms": list(preset.include),
        "exclude_terms": list(preset.exclude),
        "seniority_terms": list(preset.seniority),
        "advanced": preset.advanced,
    }


def presets_json() -> list[dict[str, Any]]:
    return [preset_json(p) for p in PRESETS]
