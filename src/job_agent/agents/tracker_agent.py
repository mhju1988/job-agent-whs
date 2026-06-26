"""Tracker Agent: manages application status transitions, follow-up reminders, and data deletion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from job_agent.tools.observability_store import ObservabilityStore

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
    obs_runs_deleted: int = 0


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
        obs: ObservabilityStore | None = None,
    ) -> None:
        self._db = db
        self._artifacts_dir = artifacts_dir
        self._clock = clock
        self._obs = obs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition(self, application_id: str, new_status: str, *, user_id: str) -> None:
        """Transition an application to a new status.

        Scoped to *user_id* so a caller can only move their own applications.
        Sets ``applied_at`` to the current clock value when moving to ``applied``.

        No observability instrumentation — this is a fast synchronous DB write,
        not an LLM agent run, so run/event rows would add noise without value.

        Raises
        ------
        LookupError
            If no application exists with the given id for this user.
        InvalidTransitionError
            If the requested status transition is not allowed.
        """
        resp = (
            self._db.raw.table("applications")
            .select("status")
            .eq("id", application_id)
            .eq("user_id", user_id)
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
            .eq("user_id", user_id)
            .execute()
        )

    def _do_check_follow_ups(self, user_id: str) -> list[str]:
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
            .eq("user_id", user_id)
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
                    .eq("user_id", user_id)
                    .execute()
                )
                updated_ids.append(row["id"])

        return sorted(updated_ids)

    def check_follow_ups(self, *, user_id: str) -> list[str]:
        """Run follow-up sweep for *user_id* with observability instrumentation."""
        from job_agent.tools.run_context import start_run

        ctx = start_run("tracker")
        if self._obs:
            self._obs.insert_run(ctx, user_id=user_id)
        try:
            result = self._do_check_follow_ups(user_id)
            if self._obs:
                self._obs.finish_run(ctx.run_id, "success")
            return result
        except Exception as exc:
            if self._obs:
                self._obs.finish_run(ctx.run_id, "error", str(exc)[:500])
            raise

    def delete_my_data(self, *, user_id: str) -> DeleteSummary:
        """Wipe one user's personal data: profile, match_scores, applications, agent_runs, files.

        Collects file paths from the user's applications rows before deletion, then
        removes each file from disk (missing_ok=True). All deletes are scoped to
        *user_id* — RLS is the hard backstop, this is defense in depth.

        No observability instrumentation — this method IS the GDPR erasure path.
        Wrapping it in an agent_run row that then gets deleted in the same call
        would cause a FK violation (llm_events → agent_runs) before the row is
        even committed.

        Returns
        -------
        DeleteSummary
            Row counts deleted from each table and number of files removed from disk.
        """
        # Collect artifact paths before deleting application rows
        apps_resp = (
            self._db.raw.table("applications")
            .select("cover_letter_path, cv_variant_path")
            .eq("user_id", user_id)
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

        # Delete only this user's rows.
        profile_resp = (
            self._db.raw.table("profile").delete().eq("user_id", user_id).execute()
        )
        profiles_deleted: int = len(profile_resp.data or [])

        matches_resp = (
            self._db.raw.table("match_scores").delete().eq("user_id", user_id).execute()
        )
        matches_deleted: int = len(matches_resp.data or [])

        applications_resp = (
            self._db.raw.table("applications").delete().eq("user_id", user_id).execute()
        )
        applications_deleted: int = len(applications_resp.data or [])

        # Delete artifact files — only paths that resolve inside artifacts_dir.
        artifact_root = self._artifacts_dir.resolve()
        files_deleted = 0
        for path_str in file_paths:
            p = Path(path_str).resolve()
            if not p.is_relative_to(artifact_root):
                continue  # skip any path that escaped the artifacts directory
            existed = p.exists()
            p.unlink(missing_ok=True)
            if existed:
                files_deleted += 1

        # Purge observability data that may contain PII (prompt_snippet carries
        # CV text). llm_events cascade-deletes via the agent_runs FK.
        obs_resp = (
            self._db.raw.table("agent_runs").delete().eq("user_id", user_id).execute()
        )
        obs_runs_deleted: int = len(obs_resp.data or [])

        return DeleteSummary(
            profiles_deleted=profiles_deleted,
            matches_deleted=matches_deleted,
            applications_deleted=applications_deleted,
            files_deleted=files_deleted,
            obs_runs_deleted=obs_runs_deleted,
        )
