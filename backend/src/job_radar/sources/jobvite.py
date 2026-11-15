"""Jobvite career sites' public XML feed (no auth).

`GET https://app.jobvite.com/CompanyJobs/Xml.aspx?c=<company id>` returns every
open job as `<result><job>...</job></result>`, no pagination. The company id is
the `c=` value in the site's Jobvite widget or feed URL; the public job page is
`jobs.jobvite.com/<careers slug>/job/<id>`. The slug is entered as
`<company id>/<careers slug>`.

Quirks:
- One row per location: a multi-location job repeats with ids
  "<base>-<suffix>", so rows are grouped by the part before the first "-".
- Fields used: id, title, location ("City, ST, United States" or a bare
  "United States"), date (M/D/YYYY), jobtype ("Full-Time").
- Some companies list jobs with no office as a bare "United States". Add that to
  `us_remote_locations` when it means remote on that board.
- The feed can be a couple of MB; it's parsed in one go.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime

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
)
from job_radar.sources.options import Option

PLATFORM_NAME = "Jobvite"
SLUG_HELP = "<company id>/<careers slug>, e.g. q6NaVfwI/tylertech"
OPTIONS = {
    "us_remote_locations": Option(
        "list", 'Location texts that mean US remote, e.g. "United States"'
    ),
}


def _ids(board: Board) -> tuple[str, str]:
    company, _, careers = board.slug.partition("/")
    return company.strip(), careers.strip() or company.strip()


def board_url(board: Board) -> str:
    return f"https://jobs.jobvite.com/{_ids(board)[1]}/jobs"


def parse_date(text: str | None) -> date | None:
    try:
        return datetime.strptime((text or "").strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


@dataclass
class _Job:
    title: str
    date: str
    job_type: str
    locations: list[str] = field(default_factory=list)


def parse_feed(xml_text: str, board: Board) -> list[RawPosting]:
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 - a public feed of job metadata
    except ET.ParseError as exc:
        raise BoardFetchError(f"{board.org}: bad Jobvite XML feed: {exc}") from exc
    remote_texts = set(board.option("us_remote_locations", []))
    careers = _ids(board)[1]

    grouped: dict[str, _Job] = {}
    for job in root.iter("job"):
        base = (job.findtext("id") or "").split("-")[0].strip()
        title = clean_title(job.findtext("title"))
        if not base or not title:
            continue
        entry = grouped.setdefault(
            base, _Job(title, job.findtext("date") or "", job.findtext("jobtype") or "")
        )
        raw = (job.findtext("location") or "").strip()
        location = US_REMOTE if raw in remote_texts else raw.removesuffix(", United States")
        if location and location not in entry.locations:
            entry.locations.append(location)

    postings: list[RawPosting] = []
    for base, entry in grouped.items():
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=base,
                title=entry.title,
                location="; ".join(entry.locations) or None,
                posted_raw=entry.date,
                posted_age_days=age_days(parse_date(entry.date)),
                url=f"https://jobs.jobvite.com/{careers}/job/{base}",
                employment_type=normalize_employment_type(entry.job_type)
                or employment_type_from_title(entry.title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    response = client.get(
        "https://app.jobvite.com/CompanyJobs/Xml.aspx",
        params={"c": _ids(board)[0]},
        timeout=60.0,
    )
    return parse_feed(response.text, board)
