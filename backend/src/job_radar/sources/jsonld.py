"""Careers pages that publish their openings as schema.org `JobPosting` JSON-LD.

Employers add this markup so search engines can list their jobs. Any page with
one or more `<script type="application/ld+json">` blocks holding `JobPosting`
objects (alone, in a list, in an `ItemList` or a `@graph`) works; the slug is
the page URL.

Location text is the address parts joined. `jobLocationType: TELECOMMUTE` is
the remote flag: a TELECOMMUTE posting with only a country ("US") reads as
"Remote - US"; one with a city keeps the city, and the location rule judges it.
`applicantLocationRequirements` naming a country does the same for remote jobs
with no address. Descriptions are never read or stored.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

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

PLATFORM_NAME = "JSON-LD careers page"
SLUG_HELP = "Full URL of a careers page with JobPosting markup"
OPTIONS: dict[str, Option] = {}


def board_url(board: Board) -> str:
    return board.slug


def _job_postings(node: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            found.append(node)
        else:
            for value in node.values():
                found += _job_postings(value)
    elif isinstance(node, list):
        for value in node:
            found += _job_postings(value)
    return found


def extract_job_postings(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    postings: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            postings += _job_postings(json.loads(script.get_text() or ""))
        except ValueError:
            continue
    return postings


def _country_name(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("name") or value.get("addressCountry")
    return str(value) if value else None


def location_of(job: dict[str, Any]) -> tuple[str, bool, str | None]:
    """-> (location text, remote flag, country)."""
    places = job.get("jobLocation") or []
    if isinstance(places, dict):
        places = [places]
    parts: list[str] = []
    country: str | None = None
    for place in places:
        address = (place.get("address") or {}) if isinstance(place, dict) else {}
        if not isinstance(address, dict):
            continue
        text = ", ".join(
            str(p) for p in (address.get("addressLocality"), address.get("addressRegion")) if p
        )
        place_country = _country_name(address.get("addressCountry"))
        country = country or place_country
        if not text and place_country:
            text = place_country
        if text and text not in parts:
            parts.append(text)
    types = job.get("jobLocationType") or []
    if isinstance(types, str):
        types = [types]
    remote = any(str(t).upper() == "TELECOMMUTE" for t in types)
    if remote and not country:
        country = _country_name(job.get("applicantLocationRequirements"))
    location = with_remote_marker("; ".join(parts), remote=remote, country=country)
    return location, remote, country


def parse_page(html: str, board: Board) -> list[RawPosting]:
    postings: list[RawPosting] = []
    seen: set[str] = set()
    for job in extract_job_postings(html):
        title = clean_title(job.get("title"))
        if not title:
            continue
        url = urljoin(board.slug, str(job.get("url") or "")) or board.slug
        key = url if url != board.slug else title
        if key in seen:
            continue
        seen.add(key)
        location, remote, _country = location_of(job)
        posted = str(job.get("datePosted") or "")
        identifier = job.get("identifier")
        if isinstance(identifier, dict):
            identifier = identifier.get("value")
        employment = job.get("employmentType")
        if isinstance(employment, list):
            employment = employment[0] if employment else None
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(identifier or key),
                title=title,
                location=location or None,
                posted_raw=posted,
                posted_age_days=age_days(parse_iso_date(posted)),
                url=url,
                workplace="remote" if remote else None,
                employment_type=normalize_employment_type(employment)
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    html = client.get(board.slug, headers={"Accept": "text/html"}).text
    if not extract_job_postings(html):
        raise BoardFetchError(f"{board.org}: no JobPosting JSON-LD found at {board.slug}")
    return parse_page(html, board)
