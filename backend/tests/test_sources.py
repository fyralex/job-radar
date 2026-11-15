"""Parser tests against recorded public board responses (tests/fixtures), plus
small inline cases for each platform's quirks."""

from __future__ import annotations

import pytest
import responses

from job_radar.http import HttpClient
from job_radar.sources import (
    PLATFORMS,
    ashby,
    breezy,
    greenhouse,
    jobvite,
    jsonld,
    lever,
    recruitee,
    teamtailor,
    workable,
)
from job_radar.sources.common import US_REMOTE, BoardFetchError, RawPosting
from tests.conftest import fixture_json, fixture_text, make_board


def _complete(postings: list[RawPosting]) -> None:
    assert postings
    for p in postings:
        assert p.title and p.title == " ".join(p.title.split())
        assert p.req_id
        assert p.url.startswith("http")
        assert p.org == "Example Org"
        assert p.board_key == "1"


class TestGreenhouse:
    def test_fixture(self) -> None:
        postings = greenhouse.parse_jobs(
            fixture_json("greenhouse.json"), make_board("greenhouse", "gitlab")
        )
        _complete(postings)
        first = postings[0]
        assert first.location == "Remote, United States"
        assert first.posted_age_days is not None
        assert first.url.startswith("https://job-boards.greenhouse.io/gitlab/jobs/")

    def test_offices_and_us_remote_locations(self) -> None:
        job = {
            "id": 1,
            "title": "Engineer",
            "location": {"name": "United States"},
            "offices": [{"name": "Remote (United States)"}],
            "absolute_url": "https://example.com/1",
        }
        board = make_board("greenhouse", "x", use_offices=True)
        assert greenhouse.parse_jobs({"jobs": [job]}, board)[0].location == (
            "United States; Remote (United States)"
        )
        board = make_board("greenhouse", "x", us_remote_locations=["United States"])
        assert greenhouse.parse_jobs({"jobs": [job]}, board)[0].location == US_REMOTE

    def test_bad_payload(self) -> None:
        with pytest.raises(BoardFetchError):
            greenhouse.parse_jobs({"error": "nope"}, make_board("greenhouse", "x"))


class TestLever:
    def test_fixture(self) -> None:
        postings = lever.parse_jobs(fixture_json("lever.json"), make_board("lever", "spotify"))
        _complete(postings)
        assert postings[0].workplace == "hybrid"
        assert postings[0].employment_type == "full_time"
        assert "/" in (postings[3].location or "")  # allLocations joined

    def test_remote_flag_and_undated(self) -> None:
        job = {
            "id": "a",
            "text": "Engineer",
            "hostedUrl": "https://jobs.lever.co/x/a",
            "workplaceType": "remote",
            "country": "US",
            "createdAt": 1_600_000_000_000,
            "categories": {"location": "United States", "allLocations": ["United States"]},
        }
        posting = lever.parse_jobs([job], make_board("lever", "x"))[0]
        assert posting.location == f"United States / {US_REMOTE}"
        assert posting.posted_age_days is not None
        undated = lever.parse_jobs([job], make_board("lever", "x", undated=True))[0]
        assert undated.posted_age_days is None

    def test_unspecified_workplace_is_none(self) -> None:
        job = {"id": "a", "text": "Engineer", "workplaceType": "unspecified", "categories": {}}
        assert lever.parse_jobs([job], make_board("lever", "x"))[0].workplace is None


class TestAshby:
    def test_fixture(self) -> None:
        postings = ashby.parse_jobs(fixture_json("ashby.json"), make_board("ashby", "linear"))
        _complete(postings)
        assert all(p.workplace == "remote" for p in postings)
        assert any(p.location and US_REMOTE in p.location for p in postings)

    def test_empty_board_is_valid(self) -> None:
        assert ashby.parse_jobs({"jobs": []}, make_board("ashby", "x")) == []

    def test_unlisted_jobs_are_skipped(self) -> None:
        payload = {"jobs": [{"id": "1", "title": "Engineer", "isListed": False}]}
        assert ashby.parse_jobs(payload, make_board("ashby", "x")) == []


class TestWorkable:
    def test_fixture_groups_rows_by_shortcode(self) -> None:
        payload = fixture_json("workable.json")
        postings = workable.parse_jobs(payload, make_board("workable", "huggingface"))
        _complete(postings)
        assert len({p.req_id for p in postings}) == len(postings)
        assert len(postings) <= len(payload["jobs"])

    def test_multi_location_rows(self) -> None:
        rows = [
            {"shortcode": "A1", "title": "Engineer", "city": "Austin", "state": "Texas",
             "country": "United States", "published_on": "2026-01-01"},
            {"shortcode": "A1", "title": "Engineer", "city": "Denver", "state": "Colorado",
             "country": "United States", "published_on": "2026-01-01"},
        ]  # fmt: skip
        postings = workable.parse_jobs({"jobs": rows}, make_board("workable", "x"))
        assert len(postings) == 1
        assert (
            postings[0].location == "Austin, Texas, United States / Denver, Colorado, United States"
        )


class TestTeamtailor:
    def test_fixture(self) -> None:
        postings = teamtailor.parse_feed(
            fixture_json("teamtailor.json"), make_board("teamtailor", "career.teamtailor.com")
        )
        _complete(postings)
        assert postings[0].employment_type == "full_time"
        assert postings[0].location and "Stockholm" in postings[0].location

    def test_board_url_accepts_scheme(self) -> None:
        board = make_board("teamtailor", "https://careers.example.com/")
        assert teamtailor.board_url(board) == "https://careers.example.com"


class TestBreezy:
    def test_fixture(self) -> None:
        postings = breezy.parse_positions(
            fixture_json("breezy.json"), make_board("breezy", "breezy-hr")
        )
        _complete(postings)

    def test_us_remote_keeps_city(self) -> None:
        pos = {
            "id": "p1",
            "name": "Engineer",
            "url": "https://x.breezy.hr/p/p1",
            "type": {"id": "fullTime", "name": "Full-Time"},
            "location": {
                "city": "Austin",
                "state": {"name": "Texas"},
                "country": {"id": "US", "name": "United States"},
                "is_remote": True,
            },
        }
        posting = breezy.parse_positions([pos], make_board("breezy", "x"))[0]
        assert posting.location == f"Austin, Texas, United States / {US_REMOTE}"
        assert posting.workplace == "remote"
        assert posting.employment_type == "full_time"


class TestJobvite:
    def test_fixture_groups_locations(self) -> None:
        board = make_board("jobvite", "q6NaVfwI/tylertech", us_remote_locations=["United States"])
        postings = jobvite.parse_feed(fixture_text("jobvite.xml"), board)
        _complete(postings)
        assert len({p.req_id for p in postings}) == len(postings)
        assert any(p.location and "; " in p.location for p in postings)
        assert any(p.location == US_REMOTE for p in postings)
        assert postings[0].url.startswith("https://jobs.jobvite.com/tylertech/job/")

    def test_bad_xml(self) -> None:
        with pytest.raises(BoardFetchError):
            jobvite.parse_feed("<result><job>", make_board("jobvite", "c/s"))


class TestRecruitee:
    def test_fixture(self) -> None:
        postings = recruitee.parse_offers(
            fixture_json("recruitee.json"), make_board("recruitee", "bunq")
        )
        _complete(postings)
        assert postings[0].workplace == "hybrid"
        assert postings[0].employment_type == "full_time"
        assert postings[0].location == "Amsterdam, Netherlands"

    def test_state_codes_only_count_in_the_us(self) -> None:
        offer = {
            "id": 1,
            "title": "Engineer",
            "remote": False,
            "locations": [
                {"city": "Austin", "state_code": "TX", "country_code": "US"},
                {"city": "Port Harcourt", "state_code": "RI", "country_code": "NG",
                 "country": "Nigeria"},
            ],
        }  # fmt: skip
        posting = recruitee.parse_offers({"offers": [offer]}, make_board("recruitee", "x"))[0]
        assert posting.location == "Austin, TX; Port Harcourt, Nigeria"

    def test_remote_only_us_when_every_location_is_us(self) -> None:
        austin = {"city": "Austin", "state_code": "TX", "country_code": "US"}
        offer = {"id": 1, "title": "Engineer", "remote": True, "locations": [austin]}
        posting = recruitee.parse_offers({"offers": [offer]}, make_board("recruitee", "x"))[0]
        assert posting.location == f"{US_REMOTE}; Austin, TX"


class TestJsonLd:
    def test_fixture(self) -> None:
        board = make_board("jsonld", "https://career.teamtailor.com/jobs/8742767")
        postings = jsonld.parse_page(fixture_text("jsonld.html"), board)
        _complete(postings)
        assert postings[0].employment_type == "full_time"

    def test_telecommute_with_only_a_country_is_us_remote(self) -> None:
        html = """<script type="application/ld+json">{"@context": "https://schema.org",
          "@graph": [{"@type": "JobPosting", "title": "Engineer", "url": "/jobs/1",
          "jobLocationType": "TELECOMMUTE",
          "applicantLocationRequirements": {"@type": "Country", "name": "US"}}]}</script>"""
        board = make_board("jsonld", "https://example.com/careers")
        posting = jsonld.parse_page(html, board)[0]
        assert posting.location == US_REMOTE
        assert posting.url == "https://example.com/jobs/1"
        assert posting.workplace == "remote"


@responses.activate
def test_fetch_board_goes_through_polite_client(client_no_wait: HttpClient) -> None:
    responses.get("https://boards-api.greenhouse.io/robots.txt", body="User-agent: *\nAllow: /\n")
    responses.get(
        "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs",
        json=fixture_json("greenhouse.json"),
    )
    postings = greenhouse.fetch_board(client_no_wait, make_board("greenhouse", "gitlab"))
    assert len(postings) == 4
    sent = responses.calls[1].request
    assert str(sent.headers["User-Agent"]).startswith("job-radar/")


def test_every_platform_exports_the_contract() -> None:
    for key, module in PLATFORMS.items():
        assert module.PLATFORM_NAME, key
        assert module.SLUG_HELP, key
        assert isinstance(module.OPTIONS, dict), key
        assert module.board_url(make_board(key, "https://example.com/x")).startswith("https://")
