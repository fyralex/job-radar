from __future__ import annotations

import pytest

from job_radar.services.location import LocationRule
from job_radar.services.work_type import (
    HYBRID,
    ONSITE,
    REMOTE,
    UNKNOWN,
    classify,
    normalize_workplace,
)

RULE = LocationRule.build(states=["TX"])


def kind(
    location: str | None, title: str = "Software Engineer", workplace: str | None = None
) -> str:
    return classify(location, title, workplace, RULE)


@pytest.mark.parametrize(
    "location, expected",
    [
        ("Austin, TX", ONSITE),
        ("Boston, MA", ONSITE),
        ("Austin, TX (Hybrid)", HYBRID),
        ("Remote - US", REMOTE),
        ("United States - Remote", REMOTE),
        ("TX - Work from home", REMOTE),
        ("Boston, MA / Remote", REMOTE),
        ("Austin, TX / Remote - US", ONSITE),  # an address in the area means on site
        ("Abingdon, England, United Kingdom", ONSITE),
        ("3 Locations", UNKNOWN),
        ("", UNKNOWN),
        (None, UNKNOWN),
    ],
)
def test_from_location(location: str | None, expected: str) -> None:
    assert kind(location) == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Software Engineer (Remote)", REMOTE),
        ("Senior Engineer - Remote", REMOTE),
        ("Remote: Data Engineer", REMOTE),
        ("Software Engineer, Hybrid", HYBRID),
        ("Remote Sensing Engineer", ONSITE),  # not a label
    ],
)
def test_from_title(title: str, expected: str) -> None:
    assert kind("Austin, TX", title) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("onsite", ONSITE),
        ("OnSite", ONSITE),
        ("Hybrid", HYBRID),
        ("Fully Remote", REMOTE),
        ("unspecified", None),
        (None, None),
    ],
)
def test_normalize_workplace(value: str | None, expected: str | None) -> None:
    assert normalize_workplace(value) == expected


def test_structured_field_wins() -> None:
    assert kind("Austin, TX", workplace="remote") == REMOTE
    assert kind("Remote - US", workplace="hybrid") == HYBRID
