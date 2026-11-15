"""Lever Postings API (documented, public, no auth).

`GET https://api.lever.co/v0/postings/<site>?mode=json` returns every open
posting as a JSON list, no pagination. The site name is the slug in the public
board URL (`jobs.lever.co/<site>`); an unknown one is a 404.

Quirks:
- `categories.location` is only the primary location; `allLocations` has all
  of them, joined here so a job open in "Dallas" or "Boston" counts for both.
- `workplaceType` ("onsite", "hybrid", "remote", "unspecified") and `country`
  are the platform's own signals; a bare "Remote" can be in Mexico, so the
  country decides whether it is US remote.
- `categories.commitment` is free text set by each company ("Full-time",
  "Full Time - Permanent", "Intern").
- `createdAt` is epoch milliseconds. Boards of evergreen requisitions have
  years-old dates that the max-age filter would always drop; the `undated`
  option ignores them (undated postings pass the age filter).
- A guessed site name can belong to another company, or hold only a test job.
  Check the public page before following a board.
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
    parse_epoch_ms,
    with_remote_marker,
)
from job_radar.sources.options import Option

PLATFORM_NAME = "Lever"
SLUG_HELP = "Site name from jobs.lever.co/<site>"
OPTIONS = {"undated": Option("bool", "Ignore posting dates (evergreen requisitions)")}


def board_url(board: Board) -> str:
    return f"https://jobs.lever.co/{board.slug}"


def _location(job: dict[str, Any]) -> str:
    categories = job.get("categories") or {}
    locations = [str(x) for x in categories.get("allLocations") or []]
    primary = categories.get("location")
    if primary and primary not in locations:
        locations.insert(0, str(primary))
    return " / ".join(locations)


def parse_jobs(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, list):
        raise BoardFetchError(f"{board.org}: unexpected Lever response")
    undated = bool(board.option("undated", False))
    postings: list[RawPosting] = []
    for job in payload:
        title = clean_title(job.get("text"))
        if not title:
            continue
        workplace = job.get("workplaceType")
        remote = workplace == "remote"
        location = with_remote_marker(_location(job), remote=remote, country=job.get("country"))
        created = None if undated else job.get("createdAt")
        commitment = (job.get("categories") or {}).get("commitment")
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(job.get("id") or ""),
                title=title,
                location=location or None,
                posted_raw=str(created or ""),
                posted_age_days=age_days(parse_epoch_ms(created)),
                url=str(job.get("hostedUrl") or board_url(board)),
                workplace=None if workplace in (None, "unspecified") else str(workplace),
                employment_type=normalize_employment_type(commitment)
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    payload = client.get_json(
        f"https://api.lever.co/v0/postings/{board.slug}", params={"mode": "json"}
    )
    return parse_jobs(payload, board)
