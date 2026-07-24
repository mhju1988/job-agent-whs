"""Admin-only endpoints: user management. Every route requires an admin JWT
(``require_admin``) and reads/writes through the service-role client
(``get_admin_db``), since owner-scoped RLS would block an admin from seeing
another user's rows. Mutations and sensitive reads are audit-logged."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from supabase_auth.types import User

from job_agent.api.deps import CurrentUser, get_admin_db, require_admin
from job_agent.api.schemas import AdminActionResponse, AdminRoleRequest, AdminUserResponse
from job_agent.db.client import SupabaseClient
from job_agent.services.admin_audit import log_admin_action
from job_agent.tools.observability_store import ObservabilityStore

router = APIRouter()


def _to_admin_user(u: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=u.id,
        email=u.email,
        created_at=u.created_at.isoformat(),
        email_confirmed=u.email_confirmed_at is not None,
        banned=bool(u.banned_until),
        role=u.app_metadata.get("role", "user"),
    )


@router.get("/admin/users")
def list_users(
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> list[AdminUserResponse]:
    users = db.raw.auth.admin.list_users()
    return [_to_admin_user(u) for u in users]


@router.post("/admin/users/{user_id}/ban")
def ban_user(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> AdminActionResponse:
    if user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot ban your own account")
    db.raw.auth.admin.update_user_by_id(user_id, {"ban_duration": "876000h"})
    log_admin_action(db, admin_user_id=admin.user_id, action="ban_user", target_user_id=user_id)
    return AdminActionResponse()


@router.post("/admin/users/{user_id}/unban")
def unban_user(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> AdminActionResponse:
    db.raw.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})
    log_admin_action(db, admin_user_id=admin.user_id, action="unban_user", target_user_id=user_id)
    return AdminActionResponse()


@router.post("/admin/users/{user_id}/confirm-email")
def confirm_email(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> AdminActionResponse:
    db.raw.auth.admin.update_user_by_id(user_id, {"email_confirm": True})
    log_admin_action(
        db, admin_user_id=admin.user_id, action="confirm_email", target_user_id=user_id
    )
    return AdminActionResponse()


@router.post("/admin/users/{user_id}/role")
def set_role(
    user_id: str,
    body: AdminRoleRequest,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> AdminActionResponse:
    if user_id == admin.user_id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote your own account")
    db.raw.auth.admin.update_user_by_id(user_id, {"app_metadata": {"role": body.role}})
    log_admin_action(
        db,
        admin_user_id=admin.user_id,
        action="set_role",
        target_user_id=user_id,
        detail={"role": body.role},
    )
    return AdminActionResponse()


@router.get("/admin/users/{user_id}/applications")
def user_applications(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> list[dict[str, Any]]:
    rows = (
        db.raw.table("applications")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    log_admin_action(
        db, admin_user_id=admin.user_id, action="view_applications", target_user_id=user_id
    )
    return cast("list[dict[str, Any]]", rows.data or [])


@router.delete("/admin/jobs/{job_id}")
def delete_job(
    job_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> AdminActionResponse:
    db.raw.table("jobs").delete().eq("id", job_id).execute()
    log_admin_action(
        db, admin_user_id=admin.user_id, action="delete_job", target_resource=job_id
    )
    return AdminActionResponse()


@router.get("/admin/observability/summary")
def observability_summary(
    admin: CurrentUser = Depends(require_admin),
    db: SupabaseClient = Depends(get_admin_db),
) -> list[dict[str, Any]]:
    result = ObservabilityStore(db=db).fetch_runs(limit=200)
    log_admin_action(db, admin_user_id=admin.user_id, action="view_observability_summary")
    return result
