"""The shapes every source module shares, plus the location-text helpers.

Every module in `job_radar.sources` turns one platform's public feed into a
list of `RawPosting`. Filtering by keyword, place and age happens later, in
`services/filters.py`, against the user's settings, so stored postings stay
complete and a settings change never needs a rescrape. Two things that only the
platform knows are written into the posting at fetch time instead:

- `workplace`: the platform's own onsite / hybrid / remote field, when it has one.
- A "Remote - US" marker in the location text, when the platform flags a posting
  as remote in the US but its text doesn't say so (see `with_remote_marker`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from job_radar.errors import BoardFetchError

__all__ = ["BoardFetchError"]  # re-exported for source modules

US_REMOTE = "Remote - US"


@dataclass(frozen=True, slots=True)
class Board:
    """One employer's board on one platform, as stored in the `boards` table.

    `slug` is the platform's company identifier (Greenhouse board token, Lever
    site name, a Teamtailor host, a careers-page URL for JSON-LD...). `options`
    holds the platform's optional switches, validated against the module's
    `OPTIONS`."""

    key: str
    org: str
    platform: str
    slug: str
    category: str = ""
    options: Mapping[str, Any] = field(default_factory=dict)

    def option(self, name: str, default: Any = None) -> Any:
        return self.options.get(name, default)


@dataclass(frozen=True, slots=True)
class RawPosting:
    board_key: str
    org: str
    category: str
    req_id: str
    title: str
    location: str | None
    posted_raw: str
    posted_age_days: int | None
    url: str
    # The platform's own workplace field ("onsite", "hybrid", "remote"), if any.
    workplace: str | None = None
    # "full_time", "part_time", "contract", "internship", "temporary", or None.
    employment_type: str | None = None


def clean_title(text: str | None) -> str:
    return " ".join((text or "").split())


def age_days(posted: date | None, today: date | None = None) -> int | None:
    if posted is None:
        return None
    return ((today or date.today()) - posted).days


def parse_iso_date(text: str | None) -> date | None:
    """'2026-09-14T13:49:24-04:00', '2026-09-29T14:23:11.388Z', '2026-10-06' -> date."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_epoch_ms(value: object) -> date | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC).date()


# --- employment type --------------------------------------------------------

FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, TEMPORARY = (
    "full_time",
    "part_time",
    "contract",
    "internship",
    "temporary",
)
EMPLOYMENT_TYPES = (FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, TEMPORARY)

_EMPLOYMENT_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bintern(ship)?s?\b|\bco-?op\b", re.IGNORECASE), INTERNSHIP),
    (re.compile(r"\bpart[- _]?time\b", re.IGNORECASE), PART_TIME),
    (re.compile(r"\bfull[- _]?time\b|\bpermanent\b|\bregular\b", re.IGNORECASE), FULL_TIME),
    (
        re.compile(r"\bcontract(or)?\b|\bfreelance\b|\bconsultant\b|\b1099\b", re.IGNORECASE),
        CONTRACT,
    ),
    (re.compile(r"\btemp(orary)?\b|\bseasonal\b|\bper[- ]diem\b", re.IGNORECASE), TEMPORARY),
)


def normalize_employment_type(value: str | None) -> str | None:
    """A platform's value ("Full-time", "FULL_TIME", "Permanent", "Contractor",
    "Internship") -> one of EMPLOYMENT_TYPES, or None if it says nothing."""
    if not value:
        return None
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value).replace("_", " ")
    for pattern, kind in _EMPLOYMENT_WORDS:
        if pattern.search(text):
            return kind
    return None


_TITLE_EMPLOYMENT: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bintern(ship)?s?\b|\bco-?op\b", re.IGNORECASE), INTERNSHIP),
    (re.compile(r"\bpart[- ]?time\b", re.IGNORECASE), PART_TIME),
    (re.compile(r"\bcontract(or)?\b|\bfreelance\b|\b1099\b", re.IGNORECASE), CONTRACT),
    (re.compile(r"\btemporary\b|\bseasonal\b", re.IGNORECASE), TEMPORARY),
)


def employment_type_from_title(title: str) -> str | None:
    """Only the clear labels: a title saying "Part-time" or "(Contract)". A plain
    title says nothing, so it stays None (shown as "type unknown")."""
    for pattern, kind in _TITLE_EMPLOYMENT:
        if pattern.search(title):
            return kind
    return None


# --- location text ----------------------------------------------------------

# Separators between locations in one string: "A; B", "A / B", "A or B",
# "A & B" ("Remote - US & Canada" is US remote on its US half) and "A | B".
LOCATION_PART_SPLIT_RE = re.compile(r";|\s/\s|\s&\s|\s*\|\s*|\s+or\s+|,\s*or\s+", re.IGNORECASE)

# "+2 more": a shortened list names no place.
MORE_RE = re.compile(r"^\s*\+\d+ more\s*$", re.IGNORECASE)

REMOTE_RE = re.compile(
    r"remote|work(ing)? (from|at) home|home office|home[- ]based|virtual|anywhere|telecommute",
    re.IGNORECASE,
)
# Lookarounds instead of \b, which can't match after the final period of "U.S.".
US_RE = re.compile(
    r"(?<![a-z])(united states( of america)?|usa|u\.s\.(a\.)?|us|north america)(?![a-z])",
    re.IGNORECASE,
)
# Words that may sit next to "remote" without naming a place. Region qualifiers
# that still cover the whole country (Northeast, Eastern time) are allowed too.
FILLER_WORDS = frozenset(
    {
        "remote", "work", "working", "from", "at", "home", "office", "virtual", "fully",
        "based", "in", "anywhere", "the", "telecommute", "northeast", "east", "coast",
        "eastern", "time", "zone", "nationwide", "within", "continental",
    }
)  # fmt: skip
# "USA-IN-Remote" is remote in Indiana only - "in" would otherwise read as filler.
_STATE_CODED_REMOTE_RE = re.compile(r"\bUSA?\s*-\s*[A-Z]{2}\s*-\s*(?i:remote)\b")
_US_COUNTRY_VALUES = frozenset({"us", "usa", "united states", "united states of america"})

STATE_NAMES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}  # fmt: skip
STATE_CODES = frozenset(STATE_NAMES.values())
_STATE_NAME_RE = re.compile(
    r"\b(" + "|".join(sorted(STATE_NAMES, key=len, reverse=True)) + r")\b", re.IGNORECASE
)
# A two-letter code counts after a separator or at the start ("Austin, TX",
# "US-TX-Austin", "TX - Austin"), or after a space at the end of a part
# ("Austin TX"), so capitalised English words ("MA OR US Remote") don't read as
# Oregon.
_CODES = "|".join(sorted(STATE_CODES))
_STATE_CODE_RE = re.compile(
    rf"(?:^|[,(/\-]\s*)({_CODES})(?![A-Za-z])|\s({_CODES})(?=\s*(?:$|[,;)]|-\s))"
)
# A part that reads as somewhere in the US: a state name or a ", XX" code.
_US_PLACE_RE = re.compile(r"\b(" + "|".join(STATE_NAMES) + r")\b|,\s*[A-Z]{2}\b", re.IGNORECASE)

# Countries other than the US that commonly appear next to city names shared
# with US cities ("Cambridge, United Kingdom", "London, Ontario, Canada").
FOREIGN_RE = re.compile(
    r"\b(uk|gbr?|united kingdom|great britain|england|scotland|ireland|canada|ontario|"
    r"india|germany|france|spain|netherlands|australia|mexico|brazil|japan|china|"
    r"singapore|israel|poland|portugal|sweden|emea|apac|latam)\b",
    re.IGNORECASE,
)


def location_parts(location: str | None) -> list[str]:
    return [
        p.strip()
        for p in LOCATION_PART_SPLIT_RE.split(location or "")
        if p.strip() and not MORE_RE.match(p)
    ]


def states_in(part: str) -> set[str]:
    """Two-letter codes of the US states a location part names."""
    states = {STATE_NAMES[m.lower()] for m in _STATE_NAME_RE.findall(part)}
    states.update(code for pair in _STATE_CODE_RE.findall(part) for code in pair if code)
    return states


def is_us_remote(location: str | None, remote: bool = False, country: str | None = None) -> bool:
    """Whether any part of a (possibly multi-location) string is remote anywhere
    in the US.

    A remote posting only counts if nothing but remote and US words is left in
    its part: "Remote - US" and "United States (Remote)" count, while "California,
    USA, Remote" and "US-AL-REMOTE" name where you must live and don't.

    `remote` is the platform's own remote flag, which makes a bare "United
    States" count. A bare "Remote" that names no country needs another sign that
    it's the US: the platform's structured `country`, or every other listed
    location being a US place (Greenhouse writes remote-in-India as "India;
    Remote")."""
    parts = location_parts(location)
    if not parts and remote and country and country.strip().lower() in _US_COUNTRY_VALUES:
        return True
    for i, part in enumerate(parts):
        if not (remote or REMOTE_RE.search(part)):
            continue
        if _STATE_CODED_REMOTE_RE.search(part):
            continue
        words = re.findall(r"[a-z]+", US_RE.sub(" ", part).lower())
        if any(w not in FILLER_WORDS for w in words):
            continue
        if US_RE.search(part):
            return True
        if country:
            if country.strip().lower() in _US_COUNTRY_VALUES:
                return True
            continue
        others = [p for j, p in enumerate(parts) if j != i]
        if all(US_RE.search(p) or _US_PLACE_RE.search(p) for p in others):
            return True
    return False


def remote_states(part: str) -> set[str]:
    """For a remote part limited to some states ("Remote - Texas", "US-TX-Remote",
    "Remote (CA, OR, WA)"), those states. Empty if the part isn't remote."""
    if not REMOTE_RE.search(part):
        return set()
    return states_in(part)


def with_remote_marker(location: str, remote: bool = False, country: str | None = None) -> str:
    """Write a platform's remote flag into the text when the text alone doesn't
    say US remote (Ashby's "United States / Canada" with isRemote set). The
    location rule only sees text."""
    if not is_us_remote(location, remote, country) or is_us_remote(location):
        return location
    return f"{location} / {US_REMOTE}" if location else US_REMOTE
