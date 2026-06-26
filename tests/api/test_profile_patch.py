"""Tests for PATCH /api/profile."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app
from job_agent.services.profile_service import ProfileUpdateResult


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_patch_returns_updated_profile() -> None:
    db = MagicMock()
    result = ProfileUpdateResult(ok=True, profile={"skills": ["Python", "SQL"], "summary": "s"})
    with patch("job_agent.api.routers.profile.update_profile_fields", return_value=result):
        r = _client(db).patch("/api/profile", json={"skills": ["Python", "SQL"]})
    assert r.status_code == 200
    assert r.json()["skills"] == ["Python", "SQL"]


def test_patch_404_when_no_profile() -> None:
    db = MagicMock()
    result = ProfileUpdateResult(ok=False, error="no profile")
    with patch("job_agent.api.routers.profile.update_profile_fields", return_value=result):
        r = _client(db).patch("/api/profile", json={"summary": "x"})
    assert r.status_code == 404


def test_patch_422_when_empty_body() -> None:
    db = MagicMock()
    r = _client(db).patch("/api/profile", json={})
    assert r.status_code == 422


def test_patch_502_on_embed_failure() -> None:
    db = MagicMock()
    result = ProfileUpdateResult(ok=False, error="embedding failed: gwdg down")
    with patch("job_agent.api.routers.profile.update_profile_fields", return_value=result):
        r = _client(db).patch("/api/profile", json={"skills": ["X"]})
    assert r.status_code == 502


def test_patch_normalizes_skills() -> None:
    db = MagicMock()
    captured: dict[str, Any] = {}

    def _fake(
        _db: Any, _user: Any, *, skills: Any = None, summary: Any = None, embedder: Any = None
    ) -> ProfileUpdateResult:
        captured["skills"] = skills
        return ProfileUpdateResult(ok=True, profile={"skills": skills})

    with patch("job_agent.api.routers.profile.update_profile_fields", side_effect=_fake):
        _client(db).patch("/api/profile", json={"skills": [" Python ", "Python", "", "SQL"]})
    assert captured["skills"] == ["Python", "SQL"]
