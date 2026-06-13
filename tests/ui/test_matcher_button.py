"""Tests for the Run Matcher Now sidebar button + Run Both composition."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from job_agent.agents.matcher_agent import MatcherResult
from job_agent.ui.app import run_matcher, run_scout_then_matcher


@contextmanager
def _patched_streamlit():
    with patch("job_agent.ui.app.st") as st_mock:
        spinner_cm = MagicMock()
        spinner_cm.__enter__ = lambda self: self
        spinner_cm.__exit__ = lambda self, *a: None
        st_mock.spinner.return_value = spinner_cm
        yield st_mock


def _db_with_profile(profile_id: str = "prof-uuid") -> MagicMock:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": profile_id}
    ]
    return db


def _db_no_profile() -> MagicMock:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = []
    return db


# ---------------------------------------------------------------------------
# run_matcher — success / zero-new / error
# ---------------------------------------------------------------------------


def test_run_matcher_success() -> None:
    """Happy path: MatcherAgent scores N jobs → st.success carries the count."""
    db = _db_with_profile()
    agent_instance = MagicMock()
    agent_instance.run.return_value = MatcherResult(
        candidates_considered=5,
        scored=5,
        persisted=5,
        errors=[],
    )

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        # Patch the source module — deferred import inside run_matcher()
        # re-resolves the name on each call, so the source-module attribute
        # IS what gets used. Patching "job_agent.ui.app.MatcherAgent" would
        # raise AttributeError because there's no module-level import.
        patch(
            "job_agent.agents.matcher_agent.MatcherAgent",
            return_value=agent_instance,
        ),
    ):
        run_matcher()

    agent_instance.run.assert_called_once_with(profile_id="prof-uuid")
    st_mock.success.assert_called_once()
    msg = st_mock.success.call_args.args[0]
    assert "Scored 5 jobs" in msg
    assert "0 errors" in msg
    st_mock.error.assert_not_called()


def test_run_matcher_zero_new_jobs_shows_clarifying_caption() -> None:
    """scored=0 is not an error — the Matcher excludes already-scored rows."""
    db = _db_with_profile()
    agent_instance = MagicMock()
    agent_instance.run.return_value = MatcherResult(
        candidates_considered=0,
        scored=0,
        persisted=0,
        errors=[],
    )

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        # Patch the source module — deferred import inside run_matcher()
        # re-resolves the name on each call, so the source-module attribute
        # IS what gets used. Patching "job_agent.ui.app.MatcherAgent" would
        # raise AttributeError because there's no module-level import.
        patch(
            "job_agent.agents.matcher_agent.MatcherAgent",
            return_value=agent_instance,
        ),
    ):
        run_matcher()

    st_mock.success.assert_called_once()
    assert "Scored 0 jobs" in st_mock.success.call_args.args[0]
    # A caption explains why scored=0 isn't an error.
    st_mock.caption.assert_called_once()
    assert "No new jobs to score" in st_mock.caption.call_args.args[0]
    st_mock.error.assert_not_called()


def test_run_matcher_mixed_success_surfaces_partial_errors() -> None:
    """scored > 0 with non-empty errors → success message reflects both counts,
    and a caption surfaces the first error so the user notices partial failure."""
    db = _db_with_profile()
    agent_instance = MagicMock()
    agent_instance.run.return_value = MatcherResult(
        candidates_considered=4,
        scored=3,
        persisted=3,
        errors=["LLM timeout on job xyz"],
    )

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        # Patch the source module — deferred import inside run_matcher()
        # re-resolves the name on each call, so the source-module attribute
        # IS what gets used. Patching "job_agent.ui.app.MatcherAgent" would
        # raise AttributeError because there's no module-level import.
        patch(
            "job_agent.agents.matcher_agent.MatcherAgent",
            return_value=agent_instance,
        ),
    ):
        run_matcher()

    # Success message carries both counts.
    st_mock.success.assert_called_once()
    msg = st_mock.success.call_args.args[0]
    assert "Scored 3 jobs" in msg
    assert "1 errors" in msg
    # The mixed-success caption surfaces the first error for visibility.
    caption_calls = [c.args[0] for c in st_mock.caption.call_args_list]
    assert any("LLM timeout on job xyz" in c for c in caption_calls)
    st_mock.error.assert_not_called()


def test_run_matcher_error_path() -> None:
    """If MatcherAgent.run raises, st.error fires and no success is shown."""
    db = _db_with_profile()
    agent_instance = MagicMock()
    agent_instance.run.side_effect = RuntimeError("gwdg embeddings down")

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        # Patch the source module — deferred import inside run_matcher()
        # re-resolves the name on each call, so the source-module attribute
        # IS what gets used. Patching "job_agent.ui.app.MatcherAgent" would
        # raise AttributeError because there's no module-level import.
        patch(
            "job_agent.agents.matcher_agent.MatcherAgent",
            return_value=agent_instance,
        ),
    ):
        run_matcher()

    st_mock.error.assert_called_once()
    assert "gwdg embeddings down" in st_mock.error.call_args.args[0]
    st_mock.success.assert_not_called()


def test_run_matcher_no_profile_shows_error() -> None:
    """Missing profile row → st.error pointing to the upload flow."""
    db = _db_no_profile()

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
    ):
        run_matcher()

    st_mock.error.assert_called_once()
    assert "No profile found" in st_mock.error.call_args.args[0]


# ---------------------------------------------------------------------------
# run_scout_then_matcher — composition
# ---------------------------------------------------------------------------


def test_run_both_calls_scout_then_matcher_in_order() -> None:
    """run_scout_then_matcher dispatches to run_scout, then run_matcher."""
    order: list[str] = []

    def fake_scout(*_a: object, **_kw: object) -> None:
        order.append("scout")

    def fake_matcher() -> None:
        order.append("matcher")

    with (
        patch("job_agent.ui.app.run_scout", side_effect=fake_scout),
        patch("job_agent.ui.app.run_matcher", side_effect=fake_matcher),
    ):
        run_scout_then_matcher(
            keyword="Python",
            location="Berlin",
            max_results=10,
            sources=["arbeitsagentur"],
        )

    assert order == ["scout", "matcher"]
