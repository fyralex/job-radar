from __future__ import annotations

import pytest

from job_radar.sources.common import (
    CONTRACT,
    FULL_TIME,
    INTERNSHIP,
    PART_TIME,
    US_REMOTE,
    employment_type_from_title,
    is_us_remote,
    location_parts,
    normalize_employment_type,
    remote_states,
    states_in,
    with_remote_marker,
)


class TestIsUsRemote:
    @pytest.mark.parametrize(
        "location",
        [
            "Remote - US",
            "United States (Remote)",
            "USA - REMOTE - REMOTE",
            "Remote",
            "Remote - U.S.",
            "Remote, United States",
            "USA-Remote",
            "United States - Northeast - Remote",
            "United States - Remote - Eastern Time",
            "US - Home-Based",
            "Remote within the Continental United States",
            "US-Remote | US-VA-Arlington | US-NC-Chapel Hill",
            "Remote; Remote - Nevada; Remote - California; +1 more",
            "Remote / Seattle, Washington",
            "Remote, Canada; Remote, United States",
        ],
    )
    def test_nationwide(self, location: str) -> None:
        assert is_us_remote(location)

    @pytest.mark.parametrize(
        "location",
        [
            "California, USA, Remote; Texas, USA, Remote",
            "US-AL-REMOTE",
            "USA-IN-Remote",
            "AK - Work from home",
            "Remote - India",
            "EMEA - Remote",
            "Seattle, WA - Remote",
            "India; Remote",
            "India; Remote; +2 more",
            "US - Home-Based - TX",
            "US-VA-Arlington | US-NC-Chapel Hill",
            "",
        ],
    )
    def test_limited_or_elsewhere(self, location: str) -> None:
        assert not is_us_remote(location)

    def test_platform_flag_and_country(self) -> None:
        assert is_us_remote("United States / Canada", remote=True, country="Canada")
        assert not is_us_remote("United States / Canada")
        assert not is_us_remote("Los Angeles, California", remote=True, country="US")
        assert not is_us_remote("Remote", country="MX")
        assert is_us_remote("San Francisco Bay Area or Remote", country="United States")
        assert is_us_remote("", remote=True, country="US")


def test_with_remote_marker() -> None:
    assert with_remote_marker("United States / Canada", remote=True) == (
        f"United States / Canada / {US_REMOTE}"
    )
    assert with_remote_marker("Remote - US", remote=True) == "Remote - US"
    assert with_remote_marker("Berlin", remote=False) == "Berlin"
    assert with_remote_marker("", remote=True, country="US") == US_REMOTE


def test_location_parts_and_states() -> None:
    assert location_parts("Austin, TX; Remote - US | +3 more") == ["Austin, TX", "Remote - US"]
    assert states_in("Austin, TX") == {"TX"}
    assert states_in("US-TX-Austin") == {"TX"}
    assert states_in("Seattle, Washington") == {"WA"}
    assert states_in("Burlington, MA OR US Remote") == {"MA"}
    assert remote_states("Remote - Texas") == {"TX"}
    assert remote_states("Austin, TX") == set()


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Full-time", FULL_TIME),
        ("FULL_TIME", FULL_TIME),
        ("FullTime", FULL_TIME),
        ("fulltime_permanent", FULL_TIME),
        ("Full Time - Permanent", FULL_TIME),
        ("Part-Time", PART_TIME),
        ("Contractor", CONTRACT),
        ("Intern", INTERNSHIP),
        ("", None),
        (None, None),
        ("Unspecified", None),
    ],
)
def test_normalize_employment_type(value: str | None, expected: str | None) -> None:
    assert normalize_employment_type(value) == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Software Engineering Intern", INTERNSHIP),
        ("Data Engineer (Contract)", CONTRACT),
        ("Part-time Developer", PART_TIME),
        ("Senior Software Engineer", None),
        ("Internal Tools Engineer", None),
    ],
)
def test_employment_type_from_title(title: str, expected: str | None) -> None:
    assert employment_type_from_title(title) == expected
