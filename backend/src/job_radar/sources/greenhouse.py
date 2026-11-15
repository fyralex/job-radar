"""Greenhouse Job Board API (documented, public, no auth).

`GET https://boards-api.greenhouse.io/v1/boards/<token>/jobs` returns every open
posting in one response, no pagination. The board token is the slug in the
public board URL (`job-boards.greenhouse.io/<token>`); an unknown token is a 404.

Quirks:
- Greenhouse has no workplace or employment-type field on the listing, so both
  come from text (`employment_type_from_title`, `services/work_type.py`).
- Some companies write a remote job's location as just "United States" and put
  "Remote (United States)" only in `offices`. Reading offices needs
  `?content=true`, a much bigger response (it carries descriptions, which are
  never stored), so it's the `use_offices` option.
- Remote-first companies may write just "United States" or "USA" for jobs open
  anywhere in the country. `us_remote_locations` lists the texts that mean
  "remote anywhere in the US" on that board.
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
    parse_iso_date,
)
from job_radar.sources.options import Option

PLATFORM_NAME = "Greenhouse"
SLUG_HELP = "Board token from job-boards.greenhouse.io/<token>"
OPTIONS = {
    "use_offices": Option("bool", "Also read each job's offices (bigger response)"),
    "us_remote_locations": Option(
        "list", 'Location texts that mean US remote, e.g. "United States"'
    ),
}


def board_url(board: Board) -> str:
    return f"https://job-boards.greenhouse.io/{board.slug}"


def job_location(job: dict[str, Any], use_offices: bool = False) -> str | None:
    parts = [str((job.get("location") or {}).get("name") or "")]
    if use_offices:
        parts += [str(o.get("name") or "") for o in job.get("offices") or []]
    unique: list[str] = []
    for part in (p.strip() for p in parts):
        if part and part not in unique:
            unique.append(part)
    return "; ".join(unique) or None


def parse_jobs(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise BoardFetchError(f"{board.org}: unexpected Greenhouse response")
    use_offices = bool(board.option("use_offices", False))
    remote_texts = set(board.option("us_remote_locations", []))
    postings: list[RawPosting] = []
    for job in payload["jobs"]:
        title = clean_title(job.get("title"))
        if not title:
            continue
        location = job_location(job, use_offices)
        if location in remote_texts:
            location = US_REMOTE
        published = str(job.get("first_published") or job.get("updated_at") or "")
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(job.get("requisition_id") or job.get("id") or ""),
                title=title,
                location=location,
                posted_raw=published,
                posted_age_days=age_days(parse_iso_date(published)),
                url=str(job.get("absolute_url") or board_url(board)),
                employment_type=employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    params = {"content": "true"} if board.option("use_offices", False) else None
    payload = client.get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{board.slug}/jobs", params=params
    )
    return parse_jobs(payload, board)
