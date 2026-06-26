"""Profile router tests: CV upload routes through the user-scoped service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app
from job_agent.services.profile_service import ProfileSaveResult


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_post_cv_streams_result_and_invokes_service_with_user_id() -> None:
    db = MagicMock()
    with patch(
        "job_agent.api.routers.profile.save_profile_from_pdf",
        return_value=ProfileSaveResult(ok=True, rescored=3),
    ) as svc:
        client = _client(db)
        with client.stream(
            "POST",
            "/api/cv",
            files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")},
        ) as r:
            body = "".join(chunk for chunk in r.iter_text())
    assert "event: result" in body
    assert '"rescored": 3' in body
    assert svc.call_args.kwargs["user_id"] == "u-1"
    assert svc.call_args.kwargs["db"] is db


def test_get_profile_returns_row() -> None:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"full_name": "Max", "skills": ["Python"]}
    ]
    client = _client(db)
    r = client.get("/api/profile")
    assert r.status_code == 200
    assert r.json()["full_name"] == "Max"
