"""Tests for the Scout-settings sidebar feature.

The action goes through `run_scout()` which:
  - looks up the cached ScoutAgent,
  - calls `scout.run(keyword=..., location=..., page_size=...)` inside an
    `st.spinner`,
  - on success shows `st.success("Fetched X jobs, upserted Y")`,
  - on failure shows `st.error`.

The UI uses friendly labels (Keywords / Max results) but maps to ScoutAgent's
existing `keyword` / `page_size` kwargs — no agent change needed.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from job_agent.agents.scout_agent import ScoutResult
from job_agent.ui.app import run_scout


@contextmanager
def _patched_streamlit():
    with patch("job_agent.ui.app.st") as st_mock:
        spinner_cm = MagicMock()
        spinner_cm.__enter__ = lambda self: self
        spinner_cm.__exit__ = lambda self, *a: None
        st_mock.spinner.return_value = spinner_cm
        yield st_mock


def _ok_result(fetched: int = 5, upserted: int = 5) -> ScoutResult:
    return ScoutResult(
        fetched=fetched,
        normalized=fetched,
        upserted=upserted,
        errors=[],
    )


# ---------------------------------------------------------------------------


def test_run_scout_button_calls_agent_with_settings() -> None:
    """UI settings flow through to ScoutAgent.run with the right kwargs."""
    scout = MagicMock()
    scout.run.return_value = _ok_result()

    with (
        _patched_streamlit(),
        patch("job_agent.ui.app.get_scout_agent", return_value=scout),
    ):
        run_scout(keyword="Java Developer", location="Oberhausen", max_results=15)

    scout.run.assert_called_once()
    kwargs = scout.run.call_args.kwargs
    assert kwargs["keyword"] == "Java Developer"
    assert kwargs["location"] == "Oberhausen"
    # UI's "max_results" maps to ScoutAgent's existing page_size kwarg.
    assert kwargs["page_size"] == 15


def test_run_scout_button_normalises_blank_strings_to_none() -> None:
    """Empty UI inputs become None so the agent uses its own defaults."""
    scout = MagicMock()
    scout.run.return_value = _ok_result()

    with (
        _patched_streamlit(),
        patch("job_agent.ui.app.get_scout_agent", return_value=scout),
    ):
        run_scout(keyword="", location="", max_results=10)

    kwargs = scout.run.call_args.kwargs
    assert kwargs["keyword"] is None
    assert kwargs["location"] is None


def test_run_scout_shows_success() -> None:
    """ScoutResult → st.success(\"Fetched X jobs, upserted Y\")."""
    scout = MagicMock()
    scout.run.return_value = _ok_result(fetched=5, upserted=5)

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_scout_agent", return_value=scout),
    ):
        run_scout(keyword="Python", location="Berlin", max_results=10)

    st_mock.success.assert_called_once()
    msg = st_mock.success.call_args.args[0]
    assert "Fetched 5 jobs" in msg
    assert "upserted 5" in msg
    st_mock.error.assert_not_called()


def test_run_scout_shows_error_on_failure() -> None:
    """If ScoutAgent.run raises, st.error fires and no success is shown."""
    scout = MagicMock()
    scout.run.side_effect = RuntimeError("rate limit exceeded")

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_scout_agent", return_value=scout),
    ):
        run_scout(keyword="Python", location="Berlin", max_results=10)

    st_mock.error.assert_called_once()
    assert "rate limit exceeded" in st_mock.error.call_args.args[0]
    st_mock.success.assert_not_called()


def test_run_scout_surfaces_normalisation_errors() -> None:
    """When ScoutResult.errors is non-empty, a caption surfaces the first one."""
    scout = MagicMock()
    scout.run.return_value = ScoutResult(
        fetched=5,
        normalized=4,
        upserted=4,
        errors=["bad row #2"],
    )

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_scout_agent", return_value=scout),
    ):
        run_scout(keyword="Python", location="Berlin", max_results=10)

    st_mock.success.assert_called_once()
    st_mock.caption.assert_called_once()
    assert "bad row #2" in st_mock.caption.call_args.args[0]
