"""Boards the user follows: validation and conversion to source `Board`s."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_radar.models import BoardRow
from job_radar.sources import PLATFORMS, get_platform
from job_radar.sources.common import Board
from job_radar.sources.options import validate_options


def to_board(row: BoardRow) -> Board:
    return Board(
        key=str(row.id),
        org=row.org,
        platform=row.platform,
        slug=row.slug,
        category=row.category,
        options=dict(row.options or {}),
    )


def clean_board_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the fields a client may set. Raises ValueError."""
    platform = str(data.get("platform", "")).strip()
    if platform not in PLATFORMS:
        raise ValueError(f"platform must be one of: {', '.join(PLATFORMS)}")
    slug = str(data.get("slug", "")).strip()
    org = str(data.get("org", "")).strip()
    if not slug:
        raise ValueError("slug is required")
    if not org:
        raise ValueError("org is required")
    if len(slug) > 500 or len(org) > 200:
        raise ValueError("slug or org is too long")
    if platform == "jsonld" and not slug.startswith(("https://", "http://")):
        raise ValueError("a JSON-LD board's slug is the careers page URL")
    options = data.get("options") or {}
    if not isinstance(options, dict):
        raise ValueError("options must be an object")
    return {
        "platform": platform,
        "slug": slug,
        "org": org,
        "category": str(data.get("category", "")).strip()[:100],
        "options": validate_options(get_platform(platform).OPTIONS, options),
        "enabled": bool(data.get("enabled", True)),
    }


def list_boards(session: Session) -> list[BoardRow]:
    return list(session.scalars(select(BoardRow).order_by(BoardRow.org, BoardRow.id)))


def board_json(row: BoardRow) -> dict[str, Any]:
    board = to_board(row)
    module = get_platform(row.platform)
    return {
        "id": row.id,
        "platform": row.platform,
        "platform_name": module.PLATFORM_NAME,
        "slug": row.slug,
        "org": row.org,
        "category": row.category,
        "options": row.options or {},
        "enabled": row.enabled,
        "url": module.board_url(board),
        "last_scraped_at": row.last_scraped_at.isoformat() if row.last_scraped_at else None,
        "last_status": row.last_status,
        "last_error": row.last_error,
        "last_count": row.last_count,
    }
