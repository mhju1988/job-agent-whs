"""Tests for the applications router (transition + document download)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.agents.tracker_agent import DeleteApplicationsSummary, InvalidTransitionError
from job_agent.api.deps import CurrentUser, get_current_user, get_user_db
from job_agent.api.main import create_app
from job_agent.config import Settings


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("u-1", "t")
    app.dependency_overrides[get_user_db] = lambda: db
    return TestClient(app)


def test_transition_calls_tracker_with_user_id() -> None:
    db = MagicMock()
    tracker = MagicMock()
    with patch("job_agent.api.routers.applications.TrackerAgent", return_value=tracker):
        r = _client(db).post("/api/applications/a-1/transition", json={"target": "applied"})
    assert r.status_code == 200
    tracker.transition.assert_called_once_with("a-1", "applied", user_id="u-1")


def test_transition_invalid_returns_409() -> None:
    db = MagicMock()
    tracker = MagicMock()
    tracker.transition.side_effect = InvalidTransitionError("bad move")
    with patch("job_agent.api.routers.applications.TrackerAgent", return_value=tracker):
        r = _client(db).post("/api/applications/a-1/transition", json={"target": "offer"})
    assert r.status_code == 409


def test_download_missing_document_returns_404(tmp_path: Path) -> None:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value
    # Path is inside artifacts_dir (passes guard) but does not exist on disk.
    missing = tmp_path / "cover_missing.docx"
    chain.execute.return_value.data = [{"cover_letter_path": str(missing)}]
    fake_settings = Settings.model_construct(artifacts_dir=tmp_path)
    with patch("job_agent.api.routers.applications.get_settings", return_value=fake_settings):
        r = _client(db).get("/api/applications/a-1/documents/cover")
    assert r.status_code == 404


def test_download_present_document_streams_file(tmp_path: Path) -> None:
    doc = tmp_path / "cover.docx"
    doc.write_bytes(b"hello")
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = [{"cover_letter_path": str(doc)}]
    fake_settings = Settings.model_construct(artifacts_dir=tmp_path)
    with patch("job_agent.api.routers.applications.get_settings", return_value=fake_settings):
        r = _client(db).get("/api/applications/a-1/documents/cover")
    assert r.status_code == 200
    assert r.content == b"hello"


def test_download_path_outside_artifacts_dir_returns_403(tmp_path: Path) -> None:
    db = MagicMock()
    chain = db.raw.table.return_value.select.return_value.eq.return_value.limit.return_value
    # Path traversal attempt: store a path outside the artifacts_dir.
    chain.execute.return_value.data = [{"cover_letter_path": "/etc/passwd"}]
    artifacts_subdir = tmp_path / "artifacts"
    artifacts_subdir.mkdir()
    fake_settings = Settings.model_construct(artifacts_dir=artifacts_subdir)
    with patch("job_agent.api.routers.applications.get_settings", return_value=fake_settings):
        r = _client(db).get("/api/applications/a-1/documents/cover")
    assert r.status_code == 403


def test_download_bad_kind_returns_400() -> None:
    db = MagicMock()
    r = _client(db).get("/api/applications/a-1/documents/banana")
    assert r.status_code == 400


def test_delete_applications_calls_tracker_and_returns_counts() -> None:
    db = MagicMock()
    tracker = MagicMock()
    tracker.delete_applications.return_value = DeleteApplicationsSummary(
        applications_deleted=2, files_deleted=3
    )
    with patch(
        "job_agent.api.routers.applications.TrackerAgent", return_value=tracker
    ):
        r = _client(db).post(
            "/api/applications/delete", json={"application_ids": ["a1", "a2"]}
        )
    assert r.status_code == 200
    assert r.json() == {"deleted": 2, "files_deleted": 3}
    tracker.delete_applications.assert_called_once_with(["a1", "a2"], user_id="u-1")
