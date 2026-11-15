"""Applications: jobs the user is pursuing, with a status history.

An application is either copied from a scraped posting (`posting_key` set) or
entered by hand for a job found elsewhere. It copies the posting's fields, so
it survives the posting closing or its board being removed.

The status only changes through `change_status`, which records an event, so
the history always explains the current status. Creation records the first
event, with `from_status` None.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from job_radar.models import ApplicationEventRow, ApplicationRow, PostingRow, utcnow
from job_radar.sources import PLATFORMS

STATUSES = (
    "saved",
    "applied",
    "screening",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "ghosted",
)
DEFAULT_STATUS = "saved"
MAX_NOTES = 20_000
MAX_NOTE = 2_000

# Fields a create or PATCH may set by hand: name -> (max length, required).
_TEXT_FIELDS: dict[str, tuple[int, bool]] = {
    "title": (500, True),
    "org": (200, True),
    "location": (500, False),
    "url": (2000, False),
    "source": (100, False),
    "notes": (MAX_NOTES, False),
}


class ApplicationExistsError(Exception):
    """The posting already has an application."""


def _text(data: dict[str, Any], name: str, limit: int, required: bool) -> str:
    value = data.get(name)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} must be at most {limit} characters")
    return value


def _check_url(url: str) -> str:
    # The UI renders this as a link, so only web addresses are allowed
    # (never javascript: or data: URLs).
    if url and (urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc):
        raise ValueError("url must start with http:// or https://")
    return url


def _status(value: Any, name: str = "status") -> str:
    if value not in STATUSES:
        raise ValueError(f"{name} must be one of: {', '.join(STATUSES)}")
    return str(value)


def _clean_fields(data: dict[str, Any], names: Sequence[str]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for name in names:
        limit, required = _TEXT_FIELDS[name]
        clean[name] = _text(data, name, limit, required)
    if "url" in clean:
        _check_url(clean["url"])
    if "location" in clean:
        clean["location"] = clean["location"] or None
    return clean


def _add_event(
    row: ApplicationRow, from_status: str | None, to_status: str, note: str, at: datetime
) -> None:
    row.events.append(
        ApplicationEventRow(from_status=from_status, to_status=to_status, note=note, at=at)
    )
    row.status = to_status
    row.updated_at = at
    if to_status == "applied" and row.applied_at is None:
        row.applied_at = at


def list_applications(session: Session, statuses: Sequence[str] = ()) -> list[ApplicationRow]:
    query = select(ApplicationRow).order_by(ApplicationRow.updated_at.desc(), ApplicationRow.id)
    if statuses:
        query = query.where(ApplicationRow.status.in_(statuses))
    return list(session.scalars(query))


def applied_posting_keys(session: Session) -> set[str]:
    """Posting keys that have an application; the Postings tab hides them."""
    query = select(ApplicationRow.posting_key).where(ApplicationRow.posting_key.is_not(None))
    return {key for key in session.scalars(query) if key}


def _has_application(session: Session, key: str) -> bool:
    query = select(ApplicationRow.id).where(ApplicationRow.posting_key == key)
    return session.scalar(query) is not None


def create_application(session: Session, data: dict[str, Any]) -> ApplicationRow:
    """Create from `posting_key` (copying the posting) or from the given fields.

    Raises ValueError for bad input and ApplicationExistsError when the posting
    already has an application."""
    status = _status(data.get("status", DEFAULT_STATUS))
    note = _text(data, "note", MAX_NOTE, False)
    key = data.get("posting_key")
    if key is not None:
        if not isinstance(key, str) or not key:
            raise ValueError("posting_key must be text")
        posting = session.scalar(select(PostingRow).where(PostingRow.posting_key == key))
        if posting is None:
            raise ValueError("no posting with that posting_key")
        if _has_application(session, key):
            raise ApplicationExistsError(key)
        platform = PLATFORMS.get(posting.board.platform)
        row = ApplicationRow(
            posting_key=key,
            title=posting.title,
            org=posting.org,
            location=posting.location,
            url=posting.url,
            source=platform.PLATFORM_NAME if platform else posting.board.platform,
            notes=_text(data, "notes", MAX_NOTES, False),
        )
    else:
        row = ApplicationRow(**_clean_fields(data, list(_TEXT_FIELDS)))
    now = utcnow()
    row.created_at = now
    _add_event(row, None, status, note, now)
    # The check above can race with another request for the same posting (a
    # double-click on "Applied"). The unique constraint is the real guard; a
    # savepoint keeps the request's session usable when it fires.
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError as exc:
        if row.posting_key is None:
            raise
        raise ApplicationExistsError(row.posting_key) from exc
    return row


def update_application(row: ApplicationRow, data: dict[str, Any]) -> ApplicationRow:
    """Edit the descriptive fields. The status changes only through events."""
    if "status" in data:
        raise ValueError("change the status by adding an event")
    unknown = set(data) - set(_TEXT_FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    for name, value in _clean_fields(data, list(data)).items():
        setattr(row, name, value)
    row.updated_at = utcnow()
    return row


def change_status(row: ApplicationRow, data: dict[str, Any]) -> ApplicationRow:
    to_status = _status(data.get("to_status"), "to_status")
    if to_status == row.status:
        raise ValueError(f"the application is already {to_status}")
    note = _text(data, "note", MAX_NOTE, False)
    _add_event(row, row.status, to_status, note, utcnow())
    return row


def event_json(event: ApplicationEventRow) -> dict[str, Any]:
    return {
        "id": event.id,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "note": event.note,
        "at": event.at.isoformat(),
    }


def application_json(row: ApplicationRow, with_events: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row.id,
        "posting_key": row.posting_key,
        "title": row.title,
        "org": row.org,
        "location": row.location,
        "url": row.url,
        "source": row.source,
        "status": row.status,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
    if with_events:
        result["events"] = [event_json(e) for e in row.events]
    return result
