"""Postings the user hid ("hidden" or "not interested")."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_radar.models import PostingMarkRow
from job_radar.services.filters import posting_key

MARK_STATUSES = ("hidden", "not_interested")


def hidden_keys(session: Session) -> set[str]:
    return set(session.scalars(select(PostingMarkRow.posting_key)))


def list_marks(session: Session) -> list[PostingMarkRow]:
    return list(session.scalars(select(PostingMarkRow).order_by(PostingMarkRow.created_at.desc())))


def add_mark(session: Session, data: dict[str, Any]) -> PostingMarkRow:
    status = str(data.get("status", ""))
    if status not in MARK_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(MARK_STATUSES)}")
    org, title = str(data.get("org", "")).strip(), str(data.get("title", "")).strip()
    if not org or not title:
        raise ValueError("org and title are required")
    location = data.get("location")
    location = str(location).strip() if location else None
    key = posting_key(org, title, location)
    row = session.get(PostingMarkRow, key)
    if row is None:
        row = PostingMarkRow(posting_key=key, org=org, title=title, location=location)
        session.add(row)
    row.status = status
    row.url = str(data.get("url", ""))[:2000]
    session.flush()
    return row


def remove_mark(session: Session, key: str) -> bool:
    row = session.get(PostingMarkRow, key)
    if row is None:
        return False
    session.delete(row)
    return True


def mark_json(row: PostingMarkRow) -> dict[str, Any]:
    return {
        "posting_key": row.posting_key,
        "status": row.status,
        "org": row.org,
        "title": row.title,
        "location": row.location,
        "url": row.url,
        "created_at": row.created_at.isoformat(),
    }
