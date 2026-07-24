"""Tests for the admin user-management endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from job_agent.api.deps import CurrentUser, get_admin_db, get_current_user
from job_agent.api.main import create_app


def _fake_user(
    uid: str = "u-2",
    email: str = "jane@example.com",
    role: str = "user",
    banned: str | None = None,
    confirmed: bool = True,
) -> SimpleNamespace:
    import datetime

    return SimpleNamespace(
        id=uid,
        email=email,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        email_confirmed_at=(
            datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC) if confirmed else None
        ),
        banned_until=banned,
        app_metadata={"role": role} if role != "user" else {},
    )


def _client(db: MagicMock, *, as_admin: bool = True) -> TestClient:
    app = create_app()
    role = "admin" if as_admin else "user"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("admin-1", "t", role)
    app.dependency_overrides[get_admin_db] = lambda: db
    return TestClient(app)


def test_non_admin_gets_403() -> None:
    db = MagicMock()
    r = _client(db, as_admin=False).get("/api/admin/users")
    assert r.status_code == 403


def test_list_users_maps_fields() -> None:
    db = MagicMock()
    db.raw.auth.admin.list_users.return_value = [_fake_user(role="admin")]
    r = _client(db).get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()[0]
    assert body["id"] == "u-2"
    assert body["email"] == "jane@example.com"
    assert body["role"] == "admin"
    assert body["email_confirmed"] is True
    assert body["banned"] is False


def test_list_users_reports_banned() -> None:
    db = MagicMock()
    db.raw.auth.admin.list_users.return_value = [_fake_user(banned="2300-01-01T00:00:00Z")]
    r = _client(db).get("/api/admin/users")
    assert r.json()[0]["banned"] is True


def test_ban_user_calls_admin_api_and_logs(monkeypatch) -> None:
    db = MagicMock()
    logged = {}
    monkeypatch.setattr(
        "job_agent.api.routers.admin.log_admin_action",
        lambda _db, **kw: logged.update(kw),
    )
    r = _client(db).post("/api/admin/users/u-2/ban")
    assert r.status_code == 200
    db.raw.auth.admin.update_user_by_id.assert_called_once_with(
        "u-2", {"ban_duration": "876000h"}
    )
    assert logged == {"admin_user_id": "admin-1", "action": "ban_user", "target_user_id": "u-2"}


def test_ban_user_blocks_self_ban() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/admin-1/ban")
    assert r.status_code == 400
    db.raw.auth.admin.update_user_by_id.assert_not_called()


def test_unban_user_calls_admin_api() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/u-2/unban")
    assert r.status_code == 200
    db.raw.auth.admin.update_user_by_id.assert_called_once_with(
        "u-2", {"ban_duration": "none"}
    )


def test_confirm_email_calls_admin_api() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/u-2/confirm-email")
    assert r.status_code == 200
    db.raw.auth.admin.update_user_by_id.assert_called_once_with(
        "u-2", {"email_confirm": True}
    )


def test_set_role_promotes_user() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/u-2/role", json={"role": "admin"})
    assert r.status_code == 200
    db.raw.auth.admin.update_user_by_id.assert_called_once_with(
        "u-2", {"app_metadata": {"role": "admin"}}
    )


def test_set_role_rejects_invalid_role() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/u-2/role", json={"role": "superuser"})
    assert r.status_code == 422


def test_set_role_blocks_self_demotion() -> None:
    db = MagicMock()
    r = _client(db).post("/api/admin/users/admin-1/role", json={"role": "user"})
    assert r.status_code == 400
    db.raw.auth.admin.update_user_by_id.assert_not_called()
