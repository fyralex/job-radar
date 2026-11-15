"""Work type of a posting: "onsite", "hybrid", "remote" or "unknown".

The platform's own workplace field wins when there is one (Lever and Ashby
`workplaceType`, Breezy's and Recruitee's remote flags, JSON-LD TELECOMMUTE).
Greenhouse and Jobvite have none, and listings carry no description, so the
rest is read from text, in this order:

1. "hybrid" in the location or title -> hybrid.
2. The title labels the job remote ("Engineer (Remote)", "... - Remote",
   "Remote: ...") -> remote. A bare word doesn't count ("Remote Sensing
   Engineer").
3. A listed location is one of the user's places and not remote-only ->
   onsite: an address in their area with no remote wording means the work is
   done there.
4. Any listed location reads as remote -> remote.
5. Any other named place -> onsite.
6. Nothing usable (empty, "3 Locations") -> unknown.
"""

from __future__ import annotations

import re

from job_radar.services.location import PLACEHOLDER_RE, LocationRule
from job_radar.sources.common import REMOTE_RE, location_parts

ONSITE, HYBRID, REMOTE, UNKNOWN = "onsite", "hybrid", "remote", "unknown"
WORK_TYPES = (ONSITE, HYBRID, REMOTE, UNKNOWN)

_HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
_TITLE_REMOTE_RE = re.compile(
    r"[(\[]\s*(fully\s+|100%\s+)?remote\b|[-–—,:|/]\s*(fully\s+)?remote\s*([)\]]|$|[-–—,|/])"  # noqa: RUF001 - dashes on purpose
    r"|^\s*remote\s*[-–—:|,]|\bremote\s*[)\]]",  # noqa: RUF001
    re.IGNORECASE,
)

_STRUCTURED = {
    "onsite": ONSITE, "on site": ONSITE, "on-site": ONSITE, "in office": ONSITE,
    "in-office": ONSITE, "in person": ONSITE, "in-person": ONSITE,
    "hybrid": HYBRID,
    "remote": REMOTE, "fully remote": REMOTE, "full remote": REMOTE, "telecommute": REMOTE,
}  # fmt: skip


def normalize_workplace(value: str | None) -> str | None:
    """'OnSite', 'Hybrid', 'Fully Remote', 'unspecified' -> a work type or None."""
    if not value:
        return None
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value.strip()).lower()
    return _STRUCTURED.get(text)


def classify(location: str | None, title: str, workplace: str | None, rule: LocationRule) -> str:
    if structured := normalize_workplace(workplace):
        return structured
    text = location or ""
    if _HYBRID_RE.search(text) or _HYBRID_RE.search(title):
        return HYBRID
    if _TITLE_REMOTE_RE.search(title):
        return REMOTE
    places = [p for p in location_parts(text) if not PLACEHOLDER_RE.search(p)]
    if not places:
        return UNKNOWN
    if not rule.any_place and rule.is_local(text):
        return ONSITE
    if any(REMOTE_RE.search(p) for p in places):
        return REMOTE
    return ONSITE
