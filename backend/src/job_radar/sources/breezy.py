"""Breezy HR boards' public JSON feed (no auth).

`GET https://<company>.breezy.hr/json` returns every published position as a
JSON list, no pagination. Each item has `id`, `name`, `url`, `published_date`
(ISO), `type` (`{"id": "fullTime", "name": "Full-Time"}`) and a structured
`location` with `city`, `state.name`, `country.id`/`country.name` and
`is_remote`.

A remote position still carries the office's city, so a US position with
`is_remote` set is labeled "Remote - US" next to the city instead of being
judged by the city alone.
"""

from __future__ import annotations

from typing import Any

from job_radar.http import HttpClient
from job_radar.sources.common import (
    US_REMOTE,
    Board,
    BoardFetchError,
    RawPosting,
    age_days,
    clean_title,
    employment_type_from_title,
    normalize_employment_type,
    parse_iso_date,
    with_remote_marker,
)
from job_radar.sources.options import Option

PLATFORM_NAME = "Breezy"
SLUG_HELP = "Company subdomain from <company>.breezy.hr"
OPTIONS: dict[str, Option] = {}


def board_url(board: Board) -> str:
    return f"https://{board.slug}.breezy.hr/"


def location_text(loc: dict[str, Any]) -> str:
    parts = [
        str(loc.get("city") or "").strip(),
        str((loc.get("state") or {}).get("name") or "").strip(),
        str((loc.get("country") or {}).get("name") or "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def parse_positions(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, list):
        raise BoardFetchError(f"{board.org}: unexpected Breezy response")
    postings: list[RawPosting] = []
    for pos in payload:
        title = clean_title(pos.get("name"))
        if not title:
            continue
        loc = pos.get("location") or {}
        location = location_text(loc)
        remote = bool(loc.get("is_remote"))
        country = str((loc.get("country") or {}).get("id") or "").strip() or None
        if remote and (country or "").upper() == "US":
            location = f"{location} / {US_REMOTE}" if location else US_REMOTE
        location = with_remote_marker(location, remote=remote, country=country)
        published = str(pos.get("published_date") or "")
        kind = pos.get("type") or {}
        employment = kind.get("name") or kind.get("id") if isinstance(kind, dict) else kind
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(pos.get("id") or pos.get("friendly_id") or title),
                title=title,
                location=location or None,
                posted_raw=published,
                posted_age_days=age_days(parse_iso_date(published)),
                url=str(pos.get("url") or board_url(board)),
                workplace="remote" if remote else None,
                employment_type=normalize_employment_type(str(employment) if employment else None)
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    return parse_positions(client.get_json(f"https://{board.slug}.breezy.hr/json"), board)
