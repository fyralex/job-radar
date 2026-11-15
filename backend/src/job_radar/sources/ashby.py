"""Ashby Posting API (documented, public, no auth).

`GET https://api.ashbyhq.com/posting-api/job-board/<name>` returns every open
posting in one response, no pagination. The name is the slug in the public
board URL (`jobs.ashbyhq.com/<name>`).

Quirks:
- An unknown name used to come back 200 with an empty `jobs` list, and later
  404. Both are handled: a 404 fails the board, and an empty list is a valid
  board with nothing open, so check the public page if a new board stays empty.
- Probing a guessed name can hit a different company that uses the same one.
  Check the organisation on the public page before following a board.
- `isRemote` / `workplaceType` and the postal address's country are the
  platform's own remote signals; they're written into the location text with
  `with_remote_marker` (e.g. "United States / Canada" with isRemote set).
- Primary and secondary locations are joined, so a job open in "San Francisco"
  or "Boston" counts for both.
- `employmentType` is "FullTime", "PartTime", "Intern", "Contract" or
  "Temporary".
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

PLATFORM_NAME = "Ashby"
SLUG_HELP = "Board name from jobs.ashbyhq.com/<name>"
OPTIONS: dict[str, Option] = {}


def board_url(board: Board) -> str:
    return f"https://jobs.ashbyhq.com/{board.slug}"


def _location(job: dict[str, Any]) -> str:
    locations = [str(job.get("location") or "")]
    locations += [str(s.get("location") or "") for s in job.get("secondaryLocations") or []]
    unique: list[str] = []
    for loc in (x.strip() for x in locations):
        if loc and loc not in unique:
            unique.append(loc)
    return " / ".join(unique)


def parse_jobs(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise BoardFetchError(f"{board.org}: unexpected Ashby response")
    postings: list[RawPosting] = []
    for job in payload["jobs"]:
        title = clean_title(job.get("title"))
        if not title or job.get("isListed") is False:
            continue
        address = (job.get("address") or {}).get("postalAddress") or {}
        workplace_raw = job.get("workplaceType")
        remote = bool(job.get("isRemote")) or workplace_raw == "Remote"
        country = address.get("addressCountry")
        location = with_remote_marker(_location(job), remote=remote, country=country)
        published = str(job.get("publishedAt") or "")
        workplace = str(workplace_raw).lower() if workplace_raw else ("remote" if remote else None)
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(job.get("id") or ""),
                title=title,
                location=location or None,
                posted_raw=published,
                posted_age_days=age_days(parse_iso_date(published)),
                url=str(job.get("jobUrl") or board_url(board)),
                workplace=workplace,
                employment_type=normalize_employment_type(job.get("employmentType"))
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    payload = client.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board.slug}")
    return parse_jobs(payload, board)
