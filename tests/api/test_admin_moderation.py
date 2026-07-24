"""Tests for admin job moderation, cross-user application view, and ops summary."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_admin_db, get_current_user
from job_agent.api.main import create_app


def _client(db: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("admin-1", "t", "admin")
    app.dependency_overrides[get_admin_db] = lambda: db
    return TestClient(app)


def test_user_applications_returns_rows_and_logs(monkeypatch) -> None:
    db = MagicMock()
    (
        db.raw.table.return_value.select.return_value.eq.return_value.order.return_value
    ).execute.return_value.data = [{"id": "a1", "user_id": "u-2", "status": "applied"}]
    logged = {}
    monkeypatch.setattr(
        "job_agent.api.routers.admin.log_admin_action",
        lambda _db, **kw: logged.update(kw),
    )
    r = _client(db).get("/api/admin/users/u-2/applications")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "a1"
    assert logged == {
        "admin_user_id": "admin-1",
        "action": "view_applications",
        "target_user_id": "u-2",
    }


def test_delete_job_deletes_and_logs(monkeypatch) -> None:
    db = MagicMock()
    logged = {}
    monkeypatch.setattr(
        "job_agent.api.routers.admin.log_admin_action",
        lambda _db, **kw: logged.update(kw),
    )
    r = _client(db).delete("/api/admin/jobs/j-9")
    assert r.status_code == 200
    db.raw.table.return_value.delete.return_value.eq.assert_called_once_with("id", "j-9")
    assert logged == {
        "admin_user_id": "admin-1",
        "action": "delete_job",
        "target_resource": "j-9",
    }


def test_observability_summary_uses_admin_db(monkeypatch) -> None:
    db = MagicMock()
    store = MagicMock()
    store.fetch_runs.return_value = [{"run_id": "r1", "user_id": "u-2"}]
    logged = {}
    monkeypatch.setattr(
        "job_agent.api.routers.admin.log_admin_action",
        lambda _db, **kw: logged.update(kw),
    )
    with patch("job_agent.api.routers.admin.ObservabilityStore", return_value=store) as ctor:
        r = _client(db).get("/api/admin/observability/summary")
    assert r.status_code == 200
    assert r.json()[0]["run_id"] == "r1"
    ctor.assert_called_once_with(db=db)
    assert logged == {
        "admin_user_id": "admin-1",
        "action": "view_observability_summary",
    }
