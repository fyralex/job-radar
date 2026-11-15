"""Workable widget feed (public, no auth).

`GET https://apply.workable.com/api/v1/widget/accounts/<account>` is the feed
behind Workable's embeddable jobs widget: every open job in one response, no
pagination. The account is the slug in `apply.workable.com/<account>/`.

Quirks:
- One row per *location*, not per job: rows are grouped by `shortcode` and
  their locations joined.
- Each row has `city`, `state` (full name), `country`, `telecommuting`,
  `published_on` (YYYY-MM-DD) and `url`. `employment_type` is present on most
  accounts ("Full-time", "Contract").
- `telecommuting` is also set on field jobs that name a city ("Territory
  Manager - Chicago"); `with_remote_marker` only marks a remote row as US
  remote when no city pins it down.
"""

from __future__ import annotations

from typing import Any

from job_radar.http import HttpClient
from job_radar.sources.common import (
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

PLATFORM_NAME = "Workable"
SLUG_HELP = "Account from apply.workable.com/<account>/"
OPTIONS: dict[str, Option] = {}


def board_url(board: Board) -> str:
    return f"https://apply.workable.com/{board.slug}/"


def _row_location(row: dict[str, Any]) -> str:
    parts = [str(row.get(k) or "").strip() for k in ("city", "state", "country")]
    return ", ".join(p for p in parts if p)


def parse_jobs(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise BoardFetchError(f"{board.org}: unexpected Workable response")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload["jobs"]:
        code = row.get("shortcode")
        if code and clean_title(row.get("title")):
            grouped.setdefault(str(code), []).append(row)

    postings: list[RawPosting] = []
    for code, rows in grouped.items():
        first = rows[0]
        locations: list[str] = []
        for row in rows:
            text = _row_location(row)
            if text and text not in locations:
                locations.append(text)
        remote = any(row.get("telecommuting") for row in rows)
        countries = {row.get("country") for row in rows}
        country = countries.pop() if len(countries) == 1 else None
        location = with_remote_marker(" / ".join(locations), remote=remote, country=country)
        published = str(first.get("published_on") or "")
        title = clean_title(first.get("title"))
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=code,
                title=title,
                location=location or None,
                posted_raw=published,
                posted_age_days=age_days(parse_iso_date(published)),
                url=str(first.get("url") or f"https://apply.workable.com/j/{code}"),
                workplace="remote" if remote and not locations else None,
                employment_type=normalize_employment_type(first.get("employment_type"))
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    payload = client.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{board.slug}")
    return parse_jobs(payload, board)
