"""Tracker Agent: manages application status transitions, follow-up reminders, and data deletion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from job_agent.db.client import SupabaseClient

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"ready_to_send"}),
    "ready_to_send": frozenset({"applied"}),
    "applied": frozenset({"interview", "rejected"}),
    "interview": frozenset({"offer", "rejected"}),
    "offer": frozenset({"rejected"}),
    "rejected": frozenset(),
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InvalidTransitionError(ValueError):
    """Raised when an application status transition is not allowed."""


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class DeleteSummary(BaseModel):
    """Summary returned by TrackerAgent.delete_my_data()."""

    model_config = ConfigDict(extra="forbid")

    profiles_deleted: int
    matches_deleted: int
    applications_deleted: int
    files_deleted: int


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TrackerAgent:
    """Manages application lifecycle: status transitions, follow-ups, and GDPR wipe.

    Parameters
    ----------
    db:            SupabaseClient (or mock for tests).
    artifacts_dir: Root directory for generated .docx artifacts.
    clock:         Callable returning current UTC datetime — inject for testability.
    """

    def __init__(
        self,
        db: SupabaseClient,
        *,
        artifacts_dir: Path = Path("artifacts"),
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._db = db
        self._artifacts_dir = artifacts_dir
        self._clock = clock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition(self, application_id: str, new_status: str) -> None:
        """Transition an application to a new status.

        Sets ``applied_at`` to the current clock value when moving to ``applied``.

        Raises
        ------
        LookupError
            If no application exists with the given id.
        InvalidTransitionError
            If the requested status transition is not allowed.
        """
        resp = (
            self._db.raw.table("applications")
            .select("status")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise LookupError(f"No application found with id={application_id!r}")

        row: dict[str, Any] = cast("dict[str, Any]", resp.data[0])
        current_status: str = row["status"]

        allowed = _ALLOWED_TRANSITIONS.get(current_status, frozenset())
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {current_status!r} to {new_status!r}. "
                f"Allowed targets: {sorted(allowed) or 'none'}."
            )

        update_payload: dict[str, Any] = {"status": new_status}
        if new_status == "applied":
            update_payload["applied_at"] = self._clock().isoformat()

        (
            self._db.raw.table("applications")
            .update(update_payload)
            .eq("id", application_id)
            .execute()
        )

    def check_follow_ups(self) -> list[str]:
        """Set ``follow_up_at`` for applied applications that are >= 7 days old.

        Queries rows where ``status='applied'``, ``follow_up_at IS NULL``, and
        ``applied_at IS NOT NULL``. For each row where
        ``(now - applied_at).days >= 7``, sets ``follow_up_at = applied_at + 7 days``.

        Returns
        -------
        list[str]
            Sorted list of application ids that were updated.
        """
        resp = (
            self._db.raw.table("applications")
            .select("id, applied_at")
            .eq("status", "applied")
            .is_("follow_up_at", "null")
            .not_.is_("applied_at", "null")
            .execute()
        )

        rows: list[dict[str, Any]] = cast("list[dict[str, Any]]", resp.data or [])
        now = self._clock()
        updated_ids: list[str] = []

        for row in rows:
            applied_at_raw: str = row["applied_at"]
            applied_at = datetime.fromisoformat(applied_at_raw)
            # Ensure timezone-aware for comparison
            if applied_at.tzinfo is None:
                applied_at = applied_at.replace(tzinfo=UTC)

            if (now - applied_at).days >= 7:
                follow_up_at = applied_at + timedelta(days=7)
                (
                    self._db.raw.table("applications")
                    .update({"follow_up_at": follow_up_at.isoformat()})
                    .eq("id", row["id"])
                    .execute()
                )
                updated_ids.append(row["id"])

        return sorted(updated_ids)

    def delete_my_data(self) -> DeleteSummary:
        """Wipe all personal data: profile, match_scores, applications, and artifact files.

        Collects file paths from applications rows before deletion, then removes each
        file from disk (missing_ok=True).

        Returns
        -------
        DeleteSummary
            Row counts deleted from each table and number of files removed from disk.
        """
        # Collect artifact paths before deleting application rows
        apps_resp = (
            self._db.raw.table("applications")
            .select("cover_letter_path, cv_variant_path")
            .execute()
        )
        app_rows: list[dict[str, Any]] = cast(
            "list[dict[str, Any]]", apps_resp.data or []
        )
        file_paths: list[str] = []
        for row in app_rows:
            for key in ("cover_letter_path", "cv_variant_path"):
                val = row.get(key)
                if val:
                    file_paths.append(str(val))

        # Delete DB rows — use a UUID-impossible sentinel so the filter is always
        # non-empty (Supabase requires a WHERE clause for DELETE) while guaranteeing
        # every real row (all valid UUIDs) is deleted.
        sentinel = "00000000-0000-0000-0000-000000000000"

        profile_resp = (
            self._db.raw.table("profile").delete().neq("id", sentinel).execute()
        )
        profiles_deleted: int = len(profile_resp.data or [])

        matches_resp = (
            self._db.raw.table("match_scores").delete().neq("id", sentinel).execute()
        )
        matches_deleted: int = len(matches_resp.data or [])

        applications_resp = (
            self._db.raw.table("applications").delete().neq("id", sentinel).execute()
        )
        applications_deleted: int = len(applications_resp.data or [])

        # Delete artifact files
        files_deleted = 0
        for path_str in file_paths:
            p = Path(path_str)
            existed = p.exists()
            p.unlink(missing_ok=True)
            if existed:
                files_deleted += 1

        return DeleteSummary(
            profiles_deleted=profiles_deleted,
            matches_deleted=matches_deleted,
            applications_deleted=applications_deleted,
            files_deleted=files_deleted,
        )
