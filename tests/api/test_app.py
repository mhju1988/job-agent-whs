"""App-factory smoke tests: health + auth enforcement + me."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_protected_route_requires_auth() -> None:
    client = TestClient(create_app())
    # No auth header → get_current_user raises 401.
    assert client.get("/api/me").status_code == 401


def test_me_returns_profile_label_and_sources() -> None:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"full_name": "Max Mustermann", "skills": ["Python", "SQL"]}
    ]
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    client = TestClient(app)

    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u-1"
    assert "Max Mustermann" in body["profile_label"]
    assert "2 skills" in body["profile_label"]
    assert body["has_profile"] is True
    assert "arbeitsagentur" in body["scout_sources"]
