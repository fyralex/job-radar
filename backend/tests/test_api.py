from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from job_radar.app import create_app
from job_radar.config import Config
from job_radar.coordination import RUN_LOCK, RedisLocks
from job_radar.models import BoardRow, utcnow
from job_radar.services.postings_repo import upsert_board_postings
from job_radar.services.settings_repo import get_settings
from job_radar.sources.common import RawPosting

pytestmark = pytest.mark.db


def _board(api: FlaskClient, **overrides: Any) -> dict[str, Any]:
    body = {"platform": "greenhouse", "slug": "acme", "org": "Acme", "category": "Tech"}
    response = api.post("/api/boards", json={**body, **overrides})
    assert response.status_code == 201, response.json
    data: dict[str, Any] = response.json
    return data


def _seed_postings(session: Session, board_id: int, postings: list[RawPosting]) -> None:
    upsert_board_postings(session, board_id, postings, utcnow())
    session.flush()


def raw(
    title: str, location: str, age: int | None = 1, employment: str | None = None
) -> RawPosting:
    return RawPosting(
        "1", "Acme", "Tech", title, title, location, "", age, "https://x", None, employment
    )


def test_health(api: FlaskClient) -> None:
    assert api.get("/api/health").json == {
        "status": "ok",
        "database": "ok",
        "redis": "not configured",
        "version": "0.1.0",
    }


def _app_with_redis(engine: Engine, sessions: sessionmaker[Session], url: str) -> FlaskClient:
    config = Config(database_url="unused", redis_url=url, testing=True)
    return create_app(config, engine=engine, sessions=sessions).test_client()


@pytest.mark.redis
def test_health_with_redis(engine: Engine, sessions: sessionmaker[Session], redis_url: str) -> None:
    response = _app_with_redis(engine, sessions, redis_url).get("/api/health")
    assert response.status_code == 200
    assert response.json["redis"] == "ok"


def test_health_with_redis_down(engine: Engine, sessions: sessionmaker[Session]) -> None:
    response = _app_with_redis(engine, sessions, "redis://127.0.0.1:1/0").get("/api/health")
    assert response.status_code == 503
    assert response.json == {
        "status": "error",
        "database": "ok",
        "redis": "unreachable",
        "version": "0.1.0",
    }


@pytest.mark.redis
def test_refreshing_follows_the_shared_run_lock(
    engine: Engine, sessions: sessionmaker[Session], redis_url: str
) -> None:
    api = _app_with_redis(engine, sessions, redis_url)
    assert api.get("/api/postings").json["refreshing"] is False
    # Another process (the worker) holds the run lock.
    worker = RedisLocks.from_url(redis_url)
    token = worker.acquire(RUN_LOCK, 60)
    assert token is not None
    assert api.get("/api/postings").json["refreshing"] is True
    assert api.post("/api/refresh").json["started"] is False
    worker.release(RUN_LOCK, token)
    assert api.get("/api/postings").json["refreshing"] is False


class TestBoards:
    def test_crud(self, api: FlaskClient) -> None:
        created = _board(api, options={"use_offices": True})
        assert created["url"] == "https://job-boards.greenhouse.io/acme"
        assert created["platform_name"] == "Greenhouse"
        assert api.get("/api/boards").json[0]["id"] == created["id"]

        patched = api.patch(f"/api/boards/{created['id']}", json={"enabled": False}).json
        assert patched["enabled"] is False
        assert patched["options"] == {"use_offices": True}

        assert api.delete(f"/api/boards/{created['id']}").status_code == 204
        assert api.get("/api/boards").json == []

    def test_duplicate_is_409(self, api: FlaskClient) -> None:
        _board(api)
        assert (
            api.post(
                "/api/boards", json={"platform": "greenhouse", "slug": "acme", "org": "Acme"}
            ).status_code
            == 409
        )

    @pytest.mark.parametrize(
        "body, message",
        [
            ({"platform": "myspace", "slug": "x", "org": "X"}, "platform must be one of"),
            ({"platform": "greenhouse", "slug": "", "org": "X"}, "slug is required"),
            (
                {"platform": "lever", "slug": "x", "org": "X", "options": {"bogus": 1}},
                "unknown option",
            ),
            (
                {"platform": "lever", "slug": "x", "org": "X", "options": {"undated": "yes"}},
                "true or false",
            ),
            ({"platform": "jsonld", "slug": "example.com", "org": "X"}, "careers page URL"),
        ],
    )
    def test_validation(self, api: FlaskClient, body: dict[str, Any], message: str) -> None:
        response = api.post("/api/boards", json=body)
        assert response.status_code == 400
        assert message in response.json["error"]

    def test_platforms(self, api: FlaskClient) -> None:
        platforms = {p["id"]: p for p in api.get("/api/platforms").json}
        assert "smartrecruiters" not in platforms
        assert platforms["lever"]["options"]["undated"]["kind"] == "bool"


class TestProfiles:
    def test_crud_and_presets(self, api: FlaskClient) -> None:
        presets = api.get("/api/profiles/presets").json
        software = next(p for p in presets if p["key"] == "software")
        created = api.post("/api/profiles", json={**software, "name": "Software"})
        assert created.status_code == 201
        second = api.post("/api/profiles", json={"name": "Frontend", "include_terms": ["react"]})
        assert second.json["position"] == created.json["position"] + 1

        updated = api.patch(
            f"/api/profiles/{second.json['id']}", json={"exclude_terms": ["intern"]}
        )
        assert updated.json["exclude_terms"] == ["intern"]
        assert updated.json["include_terms"] == ["react"]
        assert [p["name"] for p in api.get("/api/profiles").json] == ["Software", "Frontend"]
        assert api.delete(f"/api/profiles/{second.json['id']}").status_code == 204

    def test_validation(self, api: FlaskClient) -> None:
        assert api.post("/api/profiles", json={"name": "x"}).status_code == 400
        bad_regex = {"name": "x", "include_terms": ["(oops"], "advanced": True}
        assert "invalid pattern" in api.post("/api/profiles", json=bad_regex).json["error"]
        api.post("/api/profiles", json={"name": "dup", "include_terms": ["a"]})
        assert (
            api.post("/api/profiles", json={"name": "dup", "include_terms": ["a"]}).status_code
            == 409
        )


class TestSettings:
    def test_defaults_and_update(self, api: FlaskClient) -> None:
        defaults = api.get("/api/settings").json
        assert defaults["max_age_days"] == 30
        assert defaults["remote"] is True
        body = {"states": ["tx"], "cities": ["Denver, CO"], "max_age_days": 14,
                "employment_types": ["full_time"], "work_types": ["onsite", "hybrid"]}  # fmt: skip
        updated = api.put("/api/settings", json=body).json
        assert updated["states"] == ["TX"]
        assert updated["cities"] == ["Denver, CO"]
        assert updated["max_age_days"] == 14

    @pytest.mark.parametrize(
        "body",
        [
            {"states": ["ZZ"]},
            {"cities": ["Denver"]},
            {"max_age_days": 0},
            {"max_age_days": True},
            {"work_types": ["office"]},
            {"remote": "yes"},
        ],
    )
    def test_validation(self, api: FlaskClient, body: dict[str, Any]) -> None:
        assert api.put("/api/settings", json=body).status_code == 400


class TestPostings:
    def test_filters(self, api: FlaskClient, session: Session) -> None:
        board = _board(api)
        api.put("/api/settings", json={"states": ["TX"], "max_age_days": 10})
        _seed_postings(
            session,
            board["id"],
            [
                raw("Software Engineer", "Austin, TX"),
                raw("Backend Engineer", "Remote - US"),
                raw("Software Engineer II", "Seattle, WA"),
                raw("Old Software Engineer", "Austin, TX", age=40),
                raw("Software Engineer, Contract", "Austin, TX", employment="contract"),
                raw("Accountant", "Austin, TX"),
            ],
        )
        titles = {p["title"] for p in api.get("/api/postings").json["postings"]}
        assert titles == {"Software Engineer", "Backend Engineer", "Software Engineer, Contract",
                          "Accountant"}  # fmt: skip

        profile = api.post(
            "/api/profiles", json={"name": "Dev", "include_terms": ["engineer"]}
        ).json
        data = api.get(f"/api/postings?profile={profile['id']}&employmentType=full_time").json
        assert {p["title"] for p in data["postings"]} == {"Software Engineer", "Backend Engineer"}

        local = api.get("/api/postings?local=true").json["postings"]
        assert "Backend Engineer" not in {p["title"] for p in local}
        remote = api.get("/api/postings?workType=remote").json["postings"]
        assert [p["title"] for p in remote] == ["Backend Engineer"]
        assert api.get("/api/postings?maxAgeDays=60").json["postings"]

    def test_marks_hide_postings(self, api: FlaskClient, session: Session) -> None:
        board = _board(api)
        _seed_postings(session, board["id"], [raw("Engineer", "Remote - US")])
        posting = api.get("/api/postings").json["postings"][0]
        mark = api.post("/api/marks", json={**posting, "status": "not_interested"})
        assert mark.status_code == 201
        assert api.get("/api/postings").json["postings"] == []
        assert api.get("/api/marks").json[0]["title"] == "Engineer"
        key = mark.json["posting_key"]
        assert api.delete("/api/marks", query_string={"key": key}).status_code == 204
        assert len(api.get("/api/postings").json["postings"]) == 1

    def test_new_since_last_visit(self, api: FlaskClient, session: Session) -> None:
        board = _board(api)
        assert api.post("/api/visits").json["new_since"] is None
        # Pretend the first visit was an hour ago, then a new posting arrived.
        get_settings(session).last_visit_at = utcnow() - timedelta(hours=1)
        session.flush()
        _seed_postings(session, board["id"], [raw("Engineer", "Remote - US")])
        assert api.post("/api/visits").json["new_since"] is not None
        assert api.get("/api/postings").json["postings"][0]["is_new"] is True

    def test_failures_and_bad_params(self, api: FlaskClient, session: Session) -> None:
        board = _board(api)
        row = session.get(BoardRow, board["id"])
        assert row is not None
        row.last_status, row.last_error = "error", "HTTP 404"
        session.flush()
        data = api.get("/api/postings").json
        assert data["failures"] == [{"board_id": board["id"], "org": "Acme", "error": "HTTP 404"}]
        assert api.get("/api/postings?workType=office").status_code == 400
        assert api.get("/api/postings?maxAgeDays=abc").status_code == 400
        assert api.get("/api/postings?profile=999").status_code == 404
