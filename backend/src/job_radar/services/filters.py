"""Turn stored postings into what one dashboard view shows.

Order: hidden marks, location rule, max age, employment type, work type,
category, then the job profile's title match. Postings are already unique by
`posting_key` in the database, so there is no separate dedupe step here; the
same key also identifies marks.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, datetime

from job_radar.services.location import LocationRule
from job_radar.services.matching import ProfileMatcher
from job_radar.services.work_type import classify


def posting_key(org: str, title: str, location: str | None) -> str:
    """Same org + title + location = same job. Some boards list one opening
    under several requisition ids, so req_id isn't used."""
    return "|".join(" ".join(part.lower().split()) for part in (org, title, location or ""))


@dataclass(frozen=True)
class PostingView:
    """A stored posting plus everything computed for display."""

    id: int
    posting_key: str
    board_id: int
    org: str
    category: str
    title: str
    location: str | None
    url: str
    posted_on: date | None
    posted_age_days: int | None
    workplace: str | None
    work_type: str
    employment_type: str | None
    first_seen_at: datetime
    is_new: bool
    local: bool


@dataclass(frozen=True)
class ViewFilters:
    rule: LocationRule
    max_age_days: int | None = None
    employment_types: Collection[str] = ()
    work_types: Collection[str] = ()
    categories: Collection[str] = ()
    local_only: bool = False
    hidden_keys: Collection[str] = ()
    matcher: ProfileMatcher | None = None


def apply_filters(postings: Iterable[PostingView], filters: ViewFilters) -> list[PostingView]:
    kept: list[PostingView] = []
    hidden = set(filters.hidden_keys)
    for p in postings:
        if p.posting_key in hidden:
            continue
        if not filters.rule.wanted(p.location):
            continue
        if filters.local_only and not p.local:
            continue
        if (
            filters.max_age_days is not None
            and p.posted_age_days is not None
            and p.posted_age_days > filters.max_age_days
        ):
            continue
        # Unknown employment type is kept: most boards don't publish it.
        if (
            filters.employment_types
            and p.employment_type is not None
            and p.employment_type not in filters.employment_types
        ):
            continue
        if filters.work_types and p.work_type not in filters.work_types:
            continue
        if filters.categories and p.category not in filters.categories:
            continue
        if filters.matcher is not None and not filters.matcher.matches(p.title):
            continue
        kept.append(p)
    return kept


def make_view(
    *,
    id: int,
    posting_key: str,
    board_id: int,
    org: str,
    category: str,
    title: str,
    location: str | None,
    url: str,
    posted_on: date | None,
    workplace: str | None,
    employment_type: str | None,
    first_seen_at: datetime,
    rule: LocationRule,
    today: date,
    new_since: datetime | None,
) -> PostingView:
    return PostingView(
        id=id,
        posting_key=posting_key,
        board_id=board_id,
        org=org,
        category=category,
        title=title,
        location=location,
        url=url,
        posted_on=posted_on,
        posted_age_days=(today - posted_on).days if posted_on else None,
        workplace=workplace,
        work_type=classify(location, title, workplace, rule),
        employment_type=employment_type,
        first_seen_at=first_seen_at,
        is_new=new_since is not None and first_seen_at > new_since,
        local=rule.is_local(location),
    )
