"""Tests for the CV-upload → auto-rescore flow.

After a successful profile upsert, the upload handler now calls
``run_matcher(db, rescore=True)`` which (a) deletes all existing
match_scores via the UUID-sentinel pattern, (b) runs MatcherAgent
against the freshly-uploaded profile, and (c) surfaces a feedback
message that depends on the result counts.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_agent.agents.matcher_agent import MatcherResult
from job_agent.models.profile import Profile
from job_agent.tools.cv_parser import CVParser
from job_agent.ui.app import handle_cv_upload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_with_skills(*skills: str) -> Profile:
    return Profile(summary="x", skills=list(skills))


def _make_db_mock() -> MagicMock:
    """Mock db supporting profile delete/insert + match_scores delete chain."""
    db = MagicMock()
    table_mock = MagicMock()
    table_mock.delete.return_value.neq.return_value.execute.return_value.data = []
    table_mock.insert.return_value.execute.return_value.data = [{"id": "profile-uuid"}]
    db.raw.table.return_value = table_mock
    db._table_mock = table_mock
    return db


def _ok_matcher_result(scored: int = 5, errors: list[str] | None = None) -> MatcherResult:
    return MatcherResult(
        candidates_considered=scored,
        scored=scored,
        persisted=scored,
        errors=errors or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cv_upload_triggers_matcher_with_rescore_true() -> None:
    """Successful upload auto-fires run_matcher(db, rescore=True)."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = _profile_with_skills("Python")
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024
    db = _make_db_mock()

    with (
        patch("job_agent.ui.app.st") as st_mock,
        patch("job_agent.ui.app.run_matcher") as run_matcher_mock,
    ):
        run_matcher_mock.return_value = _ok_matcher_result(scored=3)
        ok = handle_cv_upload(b"%PDF...", db, parser=parser, embedder=embedder)

    assert ok is True
    run_matcher_mock.assert_called_once()
    # First positional arg is db; rescore must be True via kwarg.
    assert run_matcher_mock.call_args.kwargs.get("rescore") is True
    # st.info was called to announce the rescore.
    info_calls = [c.args[0] for c in st_mock.info.call_args_list]
    assert any("Re-scoring jobs" in m for m in info_calls)


def test_cv_upload_clears_old_scores_before_running_matcher() -> None:
    """run_matcher(rescore=True) wipes match_scores BEFORE MatcherAgent.run."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = _profile_with_skills("Python")
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024

    # Track operation order on the match_scores table.
    op_order: list[str] = []
    db = MagicMock()
    profile_table = MagicMock()
    profile_table.delete.return_value.neq.return_value.execute.return_value.data = []
    profile_table.insert.return_value.execute.return_value.data = [{"id": "profile-uuid"}]
    profile_table.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": "profile-uuid"}
    ]

    ms_table = MagicMock()

    def _ms_delete_chain() -> MagicMock:
        op_order.append("match_scores.delete")
        chain = MagicMock()
        chain.neq.return_value.execute.return_value.data = []
        return chain

    ms_table.delete.side_effect = _ms_delete_chain

    db.raw.table.side_effect = lambda name: (
        profile_table if name == "profile" else ms_table
    )

    # Stub the deferred-imported MatcherAgent so we can record its call order.
    matcher_instance = MagicMock()

    def _matcher_run(**_kw: object) -> MatcherResult:
        op_order.append("matcher.run")
        return _ok_matcher_result(scored=2)

    matcher_instance.run.side_effect = _matcher_run

    with (
        patch("job_agent.ui.app.st"),
        # Patch the source module — deferred import inside run_matcher()
        # re-resolves the name on each call.
        patch(
            "job_agent.agents.matcher_agent.MatcherAgent",
            return_value=matcher_instance,
        ),
    ):
        handle_cv_upload(b"%PDF...", db, parser=parser, embedder=embedder)

    # The delete must fire before the matcher runs.
    assert "match_scores.delete" in op_order
    assert "matcher.run" in op_order
    assert op_order.index("match_scores.delete") < op_order.index("matcher.run")


def test_cv_upload_matcher_no_unscored_jobs_shows_info() -> None:
    """When the rescore finds no jobs to score, surface a guiding st.info."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = _profile_with_skills("Python")
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024
    db = _make_db_mock()

    with (
        patch("job_agent.ui.app.st") as st_mock,
        patch("job_agent.ui.app.run_matcher") as run_matcher_mock,
    ):
        run_matcher_mock.return_value = _ok_matcher_result(scored=0, errors=[])
        handle_cv_upload(b"%PDF...", db, parser=parser, embedder=embedder)

    info_msgs = [c.args[0] for c in st_mock.info.call_args_list]
    assert any("No unscored jobs found" in m for m in info_msgs)


def test_cv_upload_matcher_partial_errors_shows_warning() -> None:
    """scored > 0 with errors → st.warning carries both counts."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = _profile_with_skills("Python")
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024
    db = _make_db_mock()

    with (
        patch("job_agent.ui.app.st") as st_mock,
        patch("job_agent.ui.app.run_matcher") as run_matcher_mock,
    ):
        run_matcher_mock.return_value = _ok_matcher_result(
            scored=2,
            errors=["one error"],
        )
        handle_cv_upload(b"%PDF...", db, parser=parser, embedder=embedder)

    st_mock.warning.assert_called_once()
    msg = st_mock.warning.call_args.args[0]
    assert "Scored 2 jobs" in msg
    assert "1 error(s)" in msg
