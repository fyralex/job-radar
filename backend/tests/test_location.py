from __future__ import annotations

import pytest

from job_radar.services.location import LocationRule, parse_city

RULE = LocationRule.build(states=["TX"], cities=["Denver, CO", "Portland, OR"])


@pytest.mark.parametrize(
    "location",
    [
        "Austin, TX",
        "Texas",
        "US-TX-Austin",
        "Denver, CO",
        "Denver",  # city only, no state named
        "Portland, Oregon",
        "Berlin; Austin, TX",
        "Remote - US",  # nationwide remote
        "Remote - Texas",  # remote limited to an allowed state
        "Hybrid - Austin, TX",
    ],
)
def test_wanted(location: str) -> None:
    assert RULE.wanted(location)


@pytest.mark.parametrize(
    "location",
    [
        "Portland, ME",  # same city name, other state
        "Seattle, WA",
        "Remote - California",  # remote limited to another state
        "Remote - India",
        "London, United Kingdom",
        "Denver, United Kingdom",  # foreign country wins over a city name
        "3 Locations",
        "",
        None,
    ],
)
def test_not_wanted(location: str | None) -> None:
    assert not RULE.wanted(location)


def test_remote_off() -> None:
    rule = LocationRule.build(states=["TX"], remote=False)
    assert not rule.wanted("Remote - US")
    assert rule.wanted("Austin, TX")


def test_remote_states_can_differ_from_on_site_states() -> None:
    rule = LocationRule.build(states=["TX"], remote_states=["CA"])
    assert rule.wanted("Remote - California")
    assert not rule.wanted("Remote - Oklahoma")


def test_keep_unknown() -> None:
    rule = LocationRule.build(states=["TX"], keep_unknown=True)
    assert rule.wanted("3 Locations")
    assert rule.wanted(None)
    assert rule.wanted("Main Campus")
    assert not rule.wanted("Seattle, WA")


def test_no_places_means_any_place() -> None:
    rule = LocationRule.build()
    assert rule.any_place
    assert rule.wanted("Berlin, Germany")
    assert rule.wanted("Seattle, WA")
    assert rule.wanted("Remote - US")
    assert not rule.wanted("3 Locations")


def test_is_local_ignores_remote_parts() -> None:
    assert RULE.is_local("Austin, TX")
    assert not RULE.is_local("Remote - Texas")
    assert not RULE.is_local("Remote - US")


def test_parse_city() -> None:
    assert parse_city("Austin, TX") == ("Austin", "TX")
    assert parse_city("Austin, tx") == ("Austin", "TX")
    assert parse_city("Austin") is None
    assert parse_city("Austin, XX") is None


def test_invalid_states_are_ignored() -> None:
    rule = LocationRule.build(states=["TX", "ZZ"], cities=["nowhere"])
    assert rule.states == frozenset({"TX"})
    assert rule.cities == ()
