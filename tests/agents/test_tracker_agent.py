"""Tests for job_agent.agents.tracker_agent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from job_agent.agents.tracker_agent import (
    _ALLOWED_TRANSITIONS,
    DeleteApplicationsSummary,
    DeleteSummary,
    InvalidTransitionError,
    TrackerAgent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
USER_ID = "00000000-0000-0000-0000-0000000000aa"


def _fixed_clock() -> datetime:
    return _FIXED_NOW


def _make_db(
    *,
    app_row: dict | None = None,
    follow_up_rows: list[dict] | None = None,
    profile_deleted: list[dict] | None = None,
    matches_deleted: list[dict] | None = None,
    apps_deleted: list[dict] | None = None,
    apps_select_rows: list[dict] | None = None,
) -> MagicMock:
    """Build a minimal SupabaseClient mock.

    Per-table mocks are cached as ``db._<name>_mock`` for post-call assertions.
    """
    db = MagicMock()

    # --- applications mock ---
    app_mock = MagicMock()

    # .select("status").eq("id",..).eq("user_id",..).limit(1).execute() → transition()
    select_status_chain = MagicMock()
    select_status_chain.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = (  # noqa: E501
        [app_row] if app_row is not None else []
    )
    app_mock.select.return_value = select_status_chain

    # .update(...).eq("id",..).eq("user_id",..).execute() → transition()
    update_chain = MagicMock()
    update_chain.eq.return_value.eq.return_value.execute.return_value.data = []
    app_mock.update.return_value = update_chain

    # .delete().eq("user_id",..).execute()  → used by delete_my_data()
    delete_chain = MagicMock()
    delete_chain.eq.return_value.execute.return_value.data = (
        apps_deleted if apps_deleted is not None else []
    )
    app_mock.delete.return_value = delete_chain

    # Store so we can swap behaviour per test
    db._app_mock = app_mock

    # --- profile mock ---
    profile_mock = MagicMock()
    profile_delete_chain = MagicMock()
    profile_delete_chain.neq.return_value.execute.return_value.data = (
        profile_deleted if profile_deleted is not None else []
    )
    profile_mock.delete.return_value = profile_delete_chain
    db._profile_mock = profile_mock

    # --- match_scores mock ---
    match_mock = MagicMock()
    match_delete_chain = MagicMock()
    match_delete_chain.neq.return_value.execute.return_value.data = (
        matches_deleted if matches_deleted is not None else []
    )
    match_mock.delete.return_value = match_delete_chain
    db._match_mock = match_mock

    table_map: dict[str, MagicMock] = {
        "applications": app_mock,
        "profile": profile_mock,
        "match_scores": match_mock,
    }
    db.raw = MagicMock()
    db.raw.table.side_effect = lambda name: table_map.get(name, MagicMock())

    return db


def _make_db_for_follow_ups(rows: list[dict]) -> MagicMock:
    """Dedicated helper: applications mock that supports the follow-up query chain.

    Query chain used in check_follow_ups:
        .select(...).eq("status","applied").eq("user_id",..).is_("follow_up_at","null")
            .not_.is_("applied_at","null").execute()
    """
    db = MagicMock()
    app_mock = MagicMock()

    # Chain: select -> eq(status) -> eq(user_id) -> is_ -> not_.is_ -> execute
    not_chain = MagicMock()
    not_chain.is_.return_value.execute.return_value.data = rows

    is_chain = MagicMock()
    is_chain.not_ = not_chain

    eq_chain = MagicMock()
    eq_chain.is_.return_value = is_chain

    app_mock.select.return_value.eq.return_value.eq.return_value = eq_chain

    # update chain: .update(...).eq("id",..).eq("user_id",..).execute()
    update_chain = MagicMock()
    update_chain.eq.return_value.eq.return_value.execute.return_value.data = []
    app_mock.update.return_value = update_chain

    db._app_mock = app_mock

    table_map: dict[str, MagicMock] = {"applications": app_mock}
    db.raw = MagicMock()
    db.raw.table.side_effect = lambda name: table_map.get(name, MagicMock())

    return db


# ---------------------------------------------------------------------------
# Transition — valid moves
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_status, to_status",
    [
        ("new", "ready_to_send"),
        ("ready_to_send", "applied"),
        ("applied", "interview"),
        ("applied", "rejected"),
        ("interview", "offer"),
        ("interview", "rejected"),
        ("offer", "rejected"),
    ],
)
def test_valid_transitions(from_status: str, to_status: str) -> None:
    db = _make_db(app_row={"status": from_status})
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    agent.transition("app-1", to_status, user_id=USER_ID)
    db._app_mock.update.assert_called_once()
    payload = db._app_mock.update.call_args[0][0]
    assert payload["status"] == to_status


# ---------------------------------------------------------------------------
# Transition — invalid moves
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_status, to_status",
    [
        ("new", "applied"),
        ("new", "interview"),
        ("new", "offer"),
        ("new", "rejected"),
        ("rejected", "applied"),
        ("rejected", "new"),
        ("applied", "new"),
        ("applied", "ready_to_send"),
        ("offer", "interview"),
        ("interview", "new"),
    ],
)
def test_invalid_transitions_raise(from_status: str, to_status: str) -> None:
    db = _make_db(app_row={"status": from_status})
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    with pytest.raises(InvalidTransitionError):
        agent.transition("app-1", to_status, user_id=USER_ID)
    # DB update must NOT have been called
    db._app_mock.update.assert_not_called()


def test_invalid_transition_message_contains_statuses() -> None:
    db = _make_db(app_row={"status": "new"})
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    with pytest.raises(InvalidTransitionError, match="new") as exc_info:
        agent.transition("app-1", "rejected", user_id=USER_ID)
    assert "rejected" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Transition — applied_at set when moving to "applied"
# ---------------------------------------------------------------------------

def test_transition_to_applied_sets_applied_at() -> None:
    db = _make_db(app_row={"status": "ready_to_send"})
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    agent.transition("app-1", "applied", user_id=USER_ID)

    payload = db._app_mock.update.call_args[0][0]
    assert payload["status"] == "applied"
    assert "applied_at" in payload
    # Should equal the injected clock value (ISO string)
    assert payload["applied_at"] == _FIXED_NOW.isoformat()


def test_transition_does_not_set_applied_at_for_other_statuses() -> None:
    db = _make_db(app_row={"status": "applied"})
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    agent.transition("app-1", "interview", user_id=USER_ID)

    payload = db._app_mock.update.call_args[0][0]
    assert "applied_at" not in payload


# ---------------------------------------------------------------------------
# Transition — missing application raises LookupError
# ---------------------------------------------------------------------------

def test_transition_missing_id_raises_lookup_error() -> None:
    db = _make_db(app_row=None)
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    with pytest.raises(LookupError, match="app-missing"):
        agent.transition("app-missing", "ready_to_send", user_id=USER_ID)


# ---------------------------------------------------------------------------
# check_follow_ups
# ---------------------------------------------------------------------------

def test_check_follow_ups_sets_follow_up_at_for_old_rows() -> None:
    old_applied_at = (_FIXED_NOW - timedelta(days=8)).isoformat()
    rows = [{"id": "app-old", "applied_at": old_applied_at}]
    db = _make_db_for_follow_ups(rows)
    agent = TrackerAgent(db=db, clock=_fixed_clock)

    updated = agent.check_follow_ups(user_id=USER_ID)

    assert updated == ["app-old"]
    db._app_mock.update.assert_called_once()
    payload = db._app_mock.update.call_args[0][0]
    assert "follow_up_at" in payload


def test_check_follow_ups_skips_recent_rows() -> None:
    recent_applied_at = (_FIXED_NOW - timedelta(days=3)).isoformat()
    rows = [{"id": "app-recent", "applied_at": recent_applied_at}]
    db = _make_db_for_follow_ups(rows)
    agent = TrackerAgent(db=db, clock=_fixed_clock)

    updated = agent.check_follow_ups(user_id=USER_ID)

    assert updated == []
    db._app_mock.update.assert_not_called()


def test_check_follow_ups_mixed_rows_only_updates_old() -> None:
    old_applied_at = (_FIXED_NOW - timedelta(days=10)).isoformat()
    recent_applied_at = (_FIXED_NOW - timedelta(days=2)).isoformat()
    rows = [
        {"id": "app-old", "applied_at": old_applied_at},
        {"id": "app-recent", "applied_at": recent_applied_at},
    ]
    db = _make_db_for_follow_ups(rows)
    agent = TrackerAgent(db=db, clock=_fixed_clock)

    updated = agent.check_follow_ups(user_id=USER_ID)

    assert updated == ["app-old"]
    assert db._app_mock.update.call_count == 1


def test_check_follow_ups_exactly_7_days_triggers_update() -> None:
    applied_at = (_FIXED_NOW - timedelta(days=7)).isoformat()
    rows = [{"id": "app-7", "applied_at": applied_at}]
    db = _make_db_for_follow_ups(rows)
    agent = TrackerAgent(db=db, clock=_fixed_clock)

    updated = agent.check_follow_ups(user_id=USER_ID)

    assert "app-7" in updated


def test_check_follow_ups_empty_returns_empty_list() -> None:
    db = _make_db_for_follow_ups([])
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    assert agent.check_follow_ups(user_id=USER_ID) == []


# ---------------------------------------------------------------------------
# delete_my_data
# ---------------------------------------------------------------------------

def _make_db_for_delete(
    *,
    app_file_rows: list[dict],
    profiles_deleted: list[dict],
    matches_deleted: list[dict],
    apps_deleted: list[dict],
    obs_runs_deleted: list[dict] | None = None,
) -> MagicMock:
    """Full mock for delete_my_data: supports both select (file paths) and delete chains."""
    db = MagicMock()

    app_mock = MagicMock()

    # .select(...).eq("user_id",..).execute()  → returns file-path rows
    select_chain = MagicMock()
    select_chain.eq.return_value.execute.return_value.data = app_file_rows
    app_mock.select.return_value = select_chain

    # .delete().eq("user_id",..).execute()
    delete_chain = MagicMock()
    delete_chain.eq.return_value.execute.return_value.data = apps_deleted
    app_mock.delete.return_value = delete_chain

    db._app_mock = app_mock

    profile_mock = MagicMock()
    p_delete_chain = MagicMock()
    p_delete_chain.eq.return_value.execute.return_value.data = profiles_deleted
    profile_mock.delete.return_value = p_delete_chain
    db._profile_mock = profile_mock

    match_mock = MagicMock()
    m_delete_chain = MagicMock()
    m_delete_chain.eq.return_value.execute.return_value.data = matches_deleted
    match_mock.delete.return_value = m_delete_chain
    db._match_mock = match_mock

    obs_mock = MagicMock()
    obs_delete_chain = MagicMock()
    obs_delete_chain.eq.return_value.execute.return_value.data = obs_runs_deleted or []
    obs_mock.delete.return_value = obs_delete_chain
    db._obs_mock = obs_mock

    table_map = {
        "applications": app_mock,
        "profile": profile_mock,
        "match_scores": match_mock,
        "agent_runs": obs_mock,
    }
    db.raw = MagicMock()
    db.raw.table.side_effect = lambda name: table_map.get(name, MagicMock())

    return db


def test_delete_my_data_removes_files_and_returns_correct_summary(
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover_letter_acme_dev.docx"
    cv = tmp_path / "cv_acme_dev.docx"
    cover.write_bytes(b"fake cover")
    cv.write_bytes(b"fake cv")

    app_file_rows = [
        {"cover_letter_path": str(cover), "cv_variant_path": str(cv)},
    ]

    db = _make_db_for_delete(
        app_file_rows=app_file_rows,
        profiles_deleted=[{"id": "p1"}],
        matches_deleted=[{"id": "m1"}, {"id": "m2"}],
        apps_deleted=[{"id": "a1"}],
        obs_runs_deleted=[{"run_id": "r1"}],
    )

    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)
    summary = agent.delete_my_data(user_id=USER_ID)

    assert isinstance(summary, DeleteSummary)
    assert summary.profiles_deleted == 1
    assert summary.matches_deleted == 2
    assert summary.applications_deleted == 1
    assert summary.files_deleted == 2
    assert summary.obs_runs_deleted == 1

    # Files must be gone
    assert not cover.exists()
    assert not cv.exists()


def test_delete_my_data_handles_missing_files_gracefully(tmp_path: Path) -> None:
    nonexistent = str(tmp_path / "ghost.docx")

    app_file_rows = [
        {"cover_letter_path": nonexistent, "cv_variant_path": None},
    ]

    db = _make_db_for_delete(
        app_file_rows=app_file_rows,
        profiles_deleted=[],
        matches_deleted=[],
        apps_deleted=[],
    )

    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)
    summary = agent.delete_my_data(user_id=USER_ID)

    # Should not raise; missing file not counted
    assert summary.files_deleted == 0


def test_delete_my_data_deletes_all_four_tables(tmp_path: Path) -> None:
    db = _make_db_for_delete(
        app_file_rows=[],
        profiles_deleted=[{"id": "p1"}, {"id": "p2"}],
        matches_deleted=[{"id": "m1"}],
        apps_deleted=[{"id": "a1"}, {"id": "a2"}, {"id": "a3"}],
        obs_runs_deleted=[{"run_id": "r1"}, {"run_id": "r2"}],
    )

    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)
    summary = agent.delete_my_data(user_id=USER_ID)

    assert summary.profiles_deleted == 2
    assert summary.matches_deleted == 1
    assert summary.applications_deleted == 3
    assert summary.files_deleted == 0
    assert summary.obs_runs_deleted == 2

    # All four delete chains were called
    db._profile_mock.delete.assert_called_once()
    db._match_mock.delete.assert_called_once()
    db._app_mock.delete.assert_called_once()
    db._obs_mock.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level exports
# ---------------------------------------------------------------------------

def test_invalid_transition_error_is_value_error() -> None:
    assert issubclass(InvalidTransitionError, ValueError)


def test_allowed_transitions_completeness() -> None:
    """Every status that can be a source must be a key; 'rejected' maps to empty set."""
    for status in ("new", "ready_to_send", "applied", "interview", "offer", "rejected"):
        assert status in _ALLOWED_TRANSITIONS
    assert _ALLOWED_TRANSITIONS["rejected"] == frozenset()


# ---------------------------------------------------------------------------
# Multi-tenancy scoping
# ---------------------------------------------------------------------------

def test_transition_scopes_lookup_and_update_to_user() -> None:
    db = _make_db(app_row={"status": "new"})
    agent = TrackerAgent(db=db, clock=_fixed_clock)

    agent.transition("app-1", "ready_to_send", user_id=USER_ID)

    # Both the status select and the update filter by user_id.
    select_eq_calls = [
        c.args for c in db._app_mock.select.return_value.eq.return_value.eq.call_args_list
    ]
    assert (("user_id", USER_ID) in select_eq_calls)
    update_eq_calls = [
        c.args for c in db._app_mock.update.return_value.eq.return_value.eq.call_args_list
    ]
    assert (("user_id", USER_ID) in update_eq_calls)


def test_delete_my_data_skips_paths_outside_artifacts_dir(tmp_path: Path) -> None:
    """Paths stored in the DB that resolve outside artifacts_dir are not unlinked."""
    # Create a file OUTSIDE artifacts_dir and a subdir to act as artifacts_dir.
    outside_file = tmp_path / "secret.docx"
    outside_file.write_bytes(b"sensitive")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    db = _make_db_for_delete(
        app_file_rows=[{"cover_letter_path": str(outside_file), "cv_variant_path": None}],
        profiles_deleted=[],
        matches_deleted=[],
        apps_deleted=[],
    )
    agent = TrackerAgent(db=db, artifacts_dir=artifacts_dir, clock=_fixed_clock)
    summary = agent.delete_my_data(user_id=USER_ID)

    assert summary.files_deleted == 0
    assert outside_file.exists(), "file outside artifacts_dir must not be deleted"


def test_delete_my_data_is_user_scoped_not_table_wipe(tmp_path: Path) -> None:
    db = _make_db_for_delete(
        app_file_rows=[],
        profiles_deleted=[{"id": "p1"}],
        matches_deleted=[{"id": "m1"}],
        apps_deleted=[{"id": "a1"}],
    )
    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)

    agent.delete_my_data(user_id=USER_ID)

    # No sentinel-based neq wipe anywhere; every delete is filtered by user_id.
    for mock in (db._app_mock, db._profile_mock, db._match_mock):
        assert mock.delete.return_value.neq.call_count == 0
        eq_calls = [c.args for c in mock.delete.return_value.eq.call_args_list]
        assert ("user_id", USER_ID) in eq_calls


# ---------------------------------------------------------------------------
# delete_applications
# ---------------------------------------------------------------------------

def _make_db_for_delete_apps(
    *, file_rows: list[dict], deleted: list[dict]
) -> MagicMock:
    """Mock supporting delete_applications: select(paths) + delete chains."""
    db = MagicMock()
    app_mock = MagicMock()
    # .select(...).eq("user_id",..).in_("id",..).execute() → path rows
    app_mock.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = (
        file_rows
    )
    # .delete().eq("user_id",..).in_("id",..).execute() → deleted rows
    app_mock.delete.return_value.eq.return_value.in_.return_value.execute.return_value.data = (
        deleted
    )
    db._app_mock = app_mock
    db.raw = MagicMock()
    db.raw.table.side_effect = lambda name: {"applications": app_mock}.get(
        name, MagicMock()
    )
    return db


def test_delete_applications_removes_rows_and_files(tmp_path: Path) -> None:
    cover = tmp_path / "cover.docx"
    cv = tmp_path / "cv.docx"
    cover.write_bytes(b"c")
    cv.write_bytes(b"v")
    db = _make_db_for_delete_apps(
        file_rows=[{"cover_letter_path": str(cover), "cv_variant_path": str(cv)}],
        deleted=[{"id": "a1"}],
    )
    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)
    summary = agent.delete_applications(["a1"], user_id=USER_ID)

    assert isinstance(summary, DeleteApplicationsSummary)
    assert summary.applications_deleted == 1
    assert summary.files_deleted == 2
    assert not cover.exists() and not cv.exists()


def test_delete_applications_empty_is_noop() -> None:
    db = MagicMock()
    agent = TrackerAgent(db=db, clock=_fixed_clock)
    summary = agent.delete_applications([], user_id=USER_ID)
    assert summary.applications_deleted == 0
    assert summary.files_deleted == 0
    db.raw.table.assert_not_called()


def test_delete_applications_scopes_to_user(tmp_path: Path) -> None:
    db = _make_db_for_delete_apps(file_rows=[], deleted=[{"id": "a1"}])
    agent = TrackerAgent(db=db, artifacts_dir=tmp_path, clock=_fixed_clock)
    agent.delete_applications(["a1"], user_id=USER_ID)
    del_eq = db._app_mock.delete.return_value.eq.call_args[0]
    assert del_eq == ("user_id", USER_ID)


def test_delete_applications_skips_files_outside_artifacts(tmp_path: Path) -> None:
    outside = tmp_path / "secret.docx"
    outside.write_bytes(b"x")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    db = _make_db_for_delete_apps(
        file_rows=[{"cover_letter_path": str(outside), "cv_variant_path": None}],
        deleted=[{"id": "a1"}],
    )
    agent = TrackerAgent(db=db, artifacts_dir=artifacts, clock=_fixed_clock)
    summary = agent.delete_applications(["a1"], user_id=USER_ID)
    assert summary.files_deleted == 0
    assert outside.exists()
