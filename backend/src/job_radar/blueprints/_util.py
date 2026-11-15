"""Small helpers shared by the blueprints."""

from __future__ import annotations

from typing import Any

from flask import abort, request


def json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="expected a JSON object body")
    return data


def int_arg(name: str, low: int, high: int) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        abort(400, description=f"{name} must be a whole number")
    if not low <= value <= high:
        abort(400, description=f"{name} must be from {low} to {high}")
    return value


def list_arg(name: str, allowed: tuple[str, ...] | None = None) -> list[str]:
    values = [v.strip() for raw in request.args.getlist(name) for v in raw.split(",") if v.strip()]
    if allowed is not None:
        bad = [v for v in values if v not in allowed]
        if bad:
            abort(400, description=f"unknown {name}: {', '.join(bad)}")
    return values


def bool_arg(name: str) -> bool:
    return request.args.get(name, "").lower() in ("1", "true", "yes")
