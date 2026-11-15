"""Teamtailor career sites' JSON Feed export (public, no auth).

`GET https://<host>/jobs.json` is a standard jsonfeed.org feed of every open
job, no pagination. Each item carries a schema.org `JobPosting` under
`_jobposting`, which has the location, dates and employment type that the bare
feed fields lack. The slug is the career site's host, e.g. `careers.example.com`
or `example.teamtailor.com`. A site that uses Teamtailor loads assets from
`teamtailor-cdn.com`.
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
)
from job_radar.sources.jsonld import location_of
from job_radar.sources.options import Option

PLATFORM_NAME = "Teamtailor"
SLUG_HELP = "Career site host, e.g. careers.example.com"
OPTIONS: dict[str, Option] = {}


def _host(board: Board) -> str:
    return board.slug.removeprefix("https://").removeprefix("http://").strip("/")


def board_url(board: Board) -> str:
    return f"https://{_host(board)}"


def parse_feed(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise BoardFetchError(f"{board.org}: unexpected Teamtailor feed")
    postings: list[RawPosting] = []
    for item in payload["items"]:
        title = clean_title(item.get("title"))
        if not title:
            continue
        job: dict[str, Any] = item.get("_jobposting") or {}
        location, remote, _country = location_of(job)
        posted = str(item.get("date_published") or job.get("datePosted") or "")
        identifier = (job.get("identifier") or {}).get("value")
        employment = job.get("employmentType")
        if isinstance(employment, list):
            employment = employment[0] if employment else None
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(identifier if identifier is not None else item.get("id") or ""),
                title=title,
                location=location or None,
                posted_raw=posted,
                posted_age_days=age_days(parse_iso_date(posted)),
                url=str(item.get("url") or board_url(board)),
                workplace="remote" if remote else None,
                employment_type=normalize_employment_type(employment)
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    return parse_feed(client.get_json(f"{board_url(board)}/jobs.json"), board)
