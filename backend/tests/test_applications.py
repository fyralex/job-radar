from __future__ import annotations

from typing import Any

import pytest
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from job_radar.models import ApplicationEventRow, ApplicationRow, BoardRow, utcnow
from job_radar.services import applications_repo
from job_radar.services.applications_repo import (
    STATUSES,
    ApplicationExistsError,
    applied_posting_keys,
    change_status,
    create_application,
    update_application,
)
from job_radar.services.filters import posting_key
from job_radar.services.postings_repo import upsert_board_postings
from job_radar.sources.common import RawPosting

pytestmark = pytest.mark.db

MANUAL = {
    "title": "Data Analyst",
    "org": "Elsewhere Inc",
    "location": "Remote",
    "url": "https://example.com/jobs/1",
    "source": "referral",
}


def _seed_posting(session: Session) -> str:
    board = BoardRow(platform="greenhouse", slug="acme", org="Acme")
    session.add(board)
    session.flush()
    posting = RawPosting(
        "1", "Acme", "Tech", "r1", "Data Engineer", "Boston, MA", "", 1, "https://x.test/1"
    )
    upsert_board_postings(session, board.id, [posting], utcnow())
    session.flush()
    return posting_key("Acme", "Data Engineer", "Boston, MA")


def _create(api: FlaskClient, **body: Any) -> dict[str, Any]:
    response = api.post("/api/applications", json=body)
    assert response.status_code == 201, response.json
    data: dict[str, Any] = response.json
    return data


class TestRepo:
    def test_manual_create_records_first_event(self, session: Session) -> None:
        row = create_application(session, {**MANUAL, "note": "found via a friend"})
        assert row.status == "saved"
        assert row.posting_key is None
        assert row.applied_at is None
        assert [(e.from_status, e.to_status, e.note) for e in row.events] == [
            (None, "saved", "found via a friend")
        ]

    def test_create_from_posting_copies_fields(self, session: Session) -> None:
        key = _seed_posting(session)
        row = create_application(session, {"posting_key": key, "status": "applied"})
        assert (row.title, row.org, row.location, row.url) == (
            "Data Engineer",
            "Acme",
            "Boston, MA",
            "https://x.test/1",
        )
        assert row.source == "Greenhouse"
        assert row.applied_at is not None

    def test_one_application_per_posting(self, session: Session) -> None:
        key = _seed_posting(session)
        create_application(session, {"posting_key": key})
        with pytest.raises(ApplicationExistsError):
            create_application(session, {"posting_key": key})

    def test_racing_create_is_a_conflict(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two requests both pass the existence check; the second hits the
        # unique constraint, which must still read as "already exists".
        key = _seed_posting(session)
        monkeypatch.setattr(applications_repo, "_has_application", lambda _s, _k: False)
        create_application(session, {"posting_key": key})
        with pytest.raises(ApplicationExistsError):
            create_application(session, {"posting_key": key})
        # The savepoint rolled back only the failed insert.
        assert session.scalar(select(func.count()).select_from(ApplicationRow)) == 1

    def test_applied_posting_keys(self, session: Session) -> None:
        key = _seed_posting(session)
        create_application(session, MANUAL)
        assert applied_posting_keys(session) == set()
        create_application(session, {"posting_key": key})
        assert applied_posting_keys(session) == {key}

    def test_unknown_posting(self, session: Session) -> None:
        with pytest.raises(ValueError, match="no posting"):
            create_application(session, {"posting_key": "nope"})

    def test_status_changes_are_recorded(self, session: Session) -> None:
        row = create_application(session, MANUAL)
        for status in ("applied", "screening", "rejected"):
            change_status(row, {"to_status": status, "note": f"now {status}"})
        session.flush()
        assert row.status == "rejected"
        assert [(e.from_status, e.to_status) for e in row.events] == [
            (None, "saved"),
            ("saved", "applied"),
            ("applied", "screening"),
            ("screening", "rejected"),
        ]
        first_applied = row.applied_at
        change_status(row, {"to_status": "applied"})
        assert row.applied_at == first_applied  # the first application date is kept

    def test_same_status_rejected(self, session: Session) -> None:
        row = create_application(session, MANUAL)
        with pytest.raises(ValueError, match="already saved"):
            change_status(row, {"to_status": "saved"})

    @pytest.mark.parametrize(
        "body, message",
        [
            ({**MANUAL, "title": " "}, "title is required"),
            ({**MANUAL, "org": ""}, "org is required"),
            ({**MANUAL, "status": "hired"}, "status must be one of"),
            ({**MANUAL, "url": "javascript:alert(1)"}, "url must start with"),
            ({**MANUAL, "url": "https://"}, "url must start with"),
            ({**MANUAL, "title": 5}, "title must be text"),
            ({**MANUAL, "title": "x" * 501}, "at most 500"),
            ({**MANUAL, "note": "x" * 2001}, "at most 2000"),
        ],
    )
    def test_validation(self, session: Session, body: dict[str, Any], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            create_application(session, body)

    def test_update_never_touches_status(self, session: Session) -> None:
        row = create_application(session, MANUAL)
        with pytest.raises(ValueError, match="adding an event"):
            update_application(row, {"status": "offer"})
        with pytest.raises(ValueError, match="unknown fields"):
            update_application(row, {"posting_key": "x"})
        update_application(row, {"notes": "  call back Monday ", "location": ""})
        assert row.notes == "call back Monday"
        assert row.location is None


class TestApi:
    def test_lifecycle(self, api: FlaskClient) -> None:
        created = _create(api, **MANUAL)
        assert created["status"] == "saved"
        assert len(created["events"]) == 1
        app_id = created["id"]

        moved = api.post(
            f"/api/applications/{app_id}/events", json={"to_status": "applied", "note": "online"}
        )
        assert moved.status_code == 201
        assert moved.json["status"] == "applied"
        assert moved.json["applied_at"] is not None
        assert moved.json["events"][-1] == {
            **moved.json["events"][-1],
            "from_status": "saved",
            "to_status": "applied",
            "note": "online",
        }

        patched = api.patch(f"/api/applications/{app_id}", json={"notes": "spoke to HR"})
        assert patched.status_code == 200
        assert patched.json["notes"] == "spoke to HR"

        listed = api.get("/api/applications").json
        assert [a["id"] for a in listed] == [app_id]
        assert "events" not in listed[0]
        assert len(api.get(f"/api/applications/{app_id}").json["events"]) == 2

        assert api.delete(f"/api/applications/{app_id}").status_code == 204
        assert api.get(f"/api/applications/{app_id}").status_code == 404

    def test_delete_removes_events(self, api: FlaskClient, session: Session) -> None:
        app_id = _create(api, **MANUAL)["id"]
        api.delete(f"/api/applications/{app_id}")
        count = session.scalar(
            select(func.count()).where(ApplicationEventRow.application_id == app_id)
        )
        assert count == 0

    def test_status_filter(self, api: FlaskClient) -> None:
        saved = _create(api, **MANUAL)
        applied = _create(api, **{**MANUAL, "title": "BI Analyst", "status": "applied"})
        assert [a["id"] for a in api.get("/api/applications?status=saved").json] == [saved["id"]]
        both = api.get("/api/applications?status=saved,applied").json
        assert {a["id"] for a in both} == {saved["id"], applied["id"]}
        bad = api.get("/api/applications?status=hired")
        assert bad.status_code == 400
        assert "unknown status" in bad.json["error"]

    def test_from_posting_and_conflict(self, api: FlaskClient, session: Session) -> None:
        key = _seed_posting(session)
        created = _create(api, posting_key=key, status="applied")
        assert created["posting_key"] == key
        again = api.post("/api/applications", json={"posting_key": key})
        assert again.status_code == 409
        assert again.json == {"error": "that posting already has an application"}

    @pytest.mark.parametrize(
        "method, path, body, status",
        [
            ("post", "/api/applications", {"title": "x"}, 400),
            ("post", "/api/applications", None, 400),
            ("patch", "/api/applications/999", {"notes": "x"}, 404),
            ("post", "/api/applications/999/events", {"to_status": "applied"}, 404),
            ("delete", "/api/applications/999", None, 404),
        ],
    )
    def test_errors_are_json(
        self, api: FlaskClient, method: str, path: str, body: Any, status: int
    ) -> None:
        response = getattr(api, method)(path, json=body)
        assert response.status_code == status
        assert isinstance(response.json["error"], str)

    def test_bad_patch_changes_nothing(self, api: FlaskClient) -> None:
        created = _create(api, **MANUAL)
        for body in (
            {"notes": "new notes", "url": "javascript:alert(1)"},
            {"notes": "new notes", "title": ""},
            {"notes": "new notes", "status": "offer"},
        ):
            response = api.patch(f"/api/applications/{created['id']}", json=body)
            assert response.status_code == 400
            assert isinstance(response.json["error"], str)
        after = api.get(f"/api/applications/{created['id']}").json
        assert after == created

    def test_applied_postings_leave_the_postings_list(
        self, api: FlaskClient, session: Session
    ) -> None:
        key = _seed_posting(session)
        assert [p["posting_key"] for p in api.get("/api/postings").json["postings"]] == [key]
        app_id = _create(api, posting_key=key, status="applied")["id"]
        assert api.get("/api/postings").json["postings"] == []
        # Deleting the application brings the posting back.
        api.delete(f"/api/applications/{app_id}")
        assert [p["posting_key"] for p in api.get("/api/postings").json["postings"]] == [key]

    def test_bad_event(self, api: FlaskClient) -> None:
        app_id = _create(api, **MANUAL)["id"]
        response = api.post(f"/api/applications/{app_id}/events", json={"to_status": "hired"})
        assert response.status_code == 400
        assert "to_status must be one of" in response.json["error"]


def test_statuses_match_the_issue() -> None:
    assert STATUSES == (
        "saved",
        "applied",
        "screening",
        "interviewing",
        "offer",
        "accepted",
        "rejected",
        "withdrawn",
        "ghosted",
    )
