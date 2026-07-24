"""Tests for the admin audit-log write helper."""

from __future__ import annotations

from unittest.mock import MagicMock

from job_agent.services.admin_audit import log_admin_action


def test_log_admin_action_inserts_expected_row() -> None:
    db = MagicMock()
    log_admin_action(
        db,
        admin_user_id="admin-1",
        action="ban_user",
        target_user_id="user-2",
        detail={"reason": "abuse report"},
    )
    db.raw.table.assert_called_once_with("admin_audit_log")
    inserted = db.raw.table.return_value.insert.call_args[0][0]
    assert inserted == {
        "admin_user_id": "admin-1",
        "action": "ban_user",
        "target_user_id": "user-2",
        "target_resource": None,
        "detail": {"reason": "abuse report"},
    }
    db.raw.table.return_value.insert.return_value.execute.assert_called_once()


def test_log_admin_action_defaults_are_none() -> None:
    db = MagicMock()
    log_admin_action(db, admin_user_id="admin-1", action="view_applications")
    inserted = db.raw.table.return_value.insert.call_args[0][0]
    assert inserted["target_user_id"] is None
    assert inserted["target_resource"] is None
    assert inserted["detail"] is None


def test_log_admin_action_swallows_insert_errors() -> None:
    db = MagicMock()
    db.raw.table.return_value.insert.return_value.execute.side_effect = Exception("boom")
    # Should not raise, even though the underlying insert failed (e.g. migration
    # 021_rbac_admin.sql not yet applied in this environment).
    log_admin_action(db, admin_user_id="admin-1", action="ban_user", target_user_id="user-2")
