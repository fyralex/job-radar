"""Recruitee careers sites' public offers API (no auth).

`GET https://<company>.recruitee.com/api/offers/` returns every published offer
in one response. Every filter parameter tried (country, city, state, remote,
limit) is ignored, so the whole feed is downloaded: one company's feed was
~4,400 offers and 53 MB, so the timeout is long. It is parsed in one go, which
is fine for one board at a time.

Each offer has `title`, `careers_url`, `published_at` ("2026-02-11 04:56:04
UTC"), `remote` / `hybrid` / `on_site`, `employment_type_code` ("fulltime_permanent") and a
`locations` list of {city, state_code, country_code}.

Quirks:
- `state_code` isn't unique across countries (a Nigerian state is "RI", a
  Uruguayan one "MA"), so the code is written into the text only next to
  country_code "US"; other countries get the country name instead.
- A remote offer can list hundreds of cities worldwide. It's US remote only when
  every listed location is in the US.
- Evergreen offers can share a months-old publish date. The `undated` option
  drops dates so the max-age filter doesn't hide every one.
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
)
from job_radar.sources.options import Option

PLATFORM_NAME = "Recruitee"
SLUG_HELP = "Company subdomain from <company>.recruitee.com"
OPTIONS = {"undated": Option("bool", "Ignore posting dates (evergreen offers)")}
MAX_LISTED_LOCATIONS = 10


def board_url(board: Board) -> str:
    return f"https://{board.slug}.recruitee.com/"


def offer_location(offer: dict[str, Any]) -> str:
    locations = offer.get("locations") or []
    parts: list[str] = []
    for loc in locations[:MAX_LISTED_LOCATIONS]:
        city = str(loc.get("city") or "").strip()
        country = str(loc.get("country_code") or "").upper()
        region = str(loc.get("state_code") or "").upper() if country == "US" else ""
        tail = region or str(loc.get("country") or country)
        text = ", ".join(p for p in (city, tail) if p)
        if text and text not in parts:
            parts.append(text)
    if len(locations) > MAX_LISTED_LOCATIONS:
        parts.append(f"+{len(locations) - MAX_LISTED_LOCATIONS} more")
    if (
        offer.get("remote")
        and locations
        and all(str(loc.get("country_code") or "").upper() == "US" for loc in locations)
    ):
        parts.insert(0, US_REMOTE)
    return "; ".join(parts)


def _workplace(offer: dict[str, Any]) -> str | None:
    if offer.get("remote"):
        return "remote"
    if offer.get("hybrid"):
        return "hybrid"
    if offer.get("on_site"):
        return "onsite"
    return None


def parse_offers(payload: object, board: Board) -> list[RawPosting]:
    if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
        raise BoardFetchError(f"{board.org}: unexpected Recruitee response")
    undated = bool(board.option("undated", False))
    postings: list[RawPosting] = []
    for offer in payload["offers"]:
        title = clean_title(offer.get("title"))
        if not title:
            continue
        published = "" if undated else str(offer.get("published_at") or "")
        postings.append(
            RawPosting(
                board_key=board.key,
                org=board.org,
                category=board.category,
                req_id=str(offer.get("id") or offer.get("slug") or ""),
                title=title,
                location=offer_location(offer) or None,
                posted_raw=published,
                posted_age_days=age_days(parse_iso_date(published[:10])),
                url=str(offer.get("careers_url") or board_url(board)),
                workplace=_workplace(offer),
                employment_type=normalize_employment_type(offer.get("employment_type_code"))
                or employment_type_from_title(title),
            )
        )
    return postings


def fetch_board(client: HttpClient, board: Board) -> list[RawPosting]:
    payload = client.get_json(f"https://{board.slug}.recruitee.com/api/offers/", timeout=120.0)
    return parse_offers(payload, board)
