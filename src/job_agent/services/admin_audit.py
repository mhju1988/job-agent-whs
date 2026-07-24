"""Audit logging for admin actions — every admin mutation or sensitive
cross-user read writes one row to ``admin_audit_log`` (migration 021)."""

from __future__ import annotations

import logging
from typing import Any

from job_agent.db.client import SupabaseClient

log = logging.getLogger(__name__)


def log_admin_action(
    db: SupabaseClient,
    *,
    admin_user_id: str,
    action: str,
    target_user_id: str | None = None,
    target_resource: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        db.raw.table("admin_audit_log").insert(
            {
                "admin_user_id": admin_user_id,
                "action": action,
                "target_user_id": target_user_id,
                "target_resource": target_resource,
                "detail": detail,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("admin audit log insert failed (migration pending?): %s", exc)
