"""Tests for the Prepare-Application action in the Matches tab.

The action goes through `_run_writer()` which:
  - looks up the single profile row,
  - calls `WriterAgent.run()` inside an `st.spinner`,
  - on success shows `st.success` + two `st.download_button`s,
  - on failure shows `st.error`.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from job_agent.agents.writer_agent import WriterResult
from job_agent.ui.app import _run_writer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _db_with_profile(profile_id: str = "prof-uuid") -> MagicMock:
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"id": profile_id}
    ]
    return db


def _writer_result(app_id: str = "app-1") -> WriterResult:
    return WriterResult(
        application_id=app_id,
        cover_letter_path=str(Path("/tmp/cover.docx")),
        cv_variant_path=str(Path("/tmp/cv.docx")),
        status="ready_to_send",
    )


@contextmanager
def _patched_streamlit():
    """Patch app.st so spinner/success/error/download_button are observable."""
    with patch("job_agent.ui.app.st") as st_mock:
        # Spinner is used as a context manager.
        spinner_cm = MagicMock()
        spinner_cm.__enter__ = lambda self: self
        spinner_cm.__exit__ = lambda self, *a: None
        st_mock.spinner.return_value = spinner_cm
        yield st_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prepare_button_triggers_writer() -> None:
    """_run_writer calls WriterAgent.run with the right job_id + matched_skills."""
    db = _db_with_profile()
    writer = MagicMock()
    writer.run.return_value = _writer_result()

    with (
        _patched_streamlit(),
        patch("job_agent.ui.app.get_db", return_value=db),
        patch("job_agent.ui.app.get_writer_agent", return_value=writer),
        patch("builtins.open", mock_open(read_data=b"x")),
    ):
        _run_writer(
            job_id="job-42",
            match_score_id="ms-99",
            matched_skills=["Python", "SQL"],
        )

    writer.run.assert_called_once()
    kwargs = writer.run.call_args.kwargs
    assert kwargs["job_id"] == "job-42"
    assert kwargs["match_score_id"] == "ms-99"
    assert kwargs["matched_skills"] == ["Python", "SQL"]
    assert kwargs["profile_id"] == "prof-uuid"


def test_prepare_button_shows_download_on_success() -> None:
    """On success: st.success called + two st.download_button calls."""
    db = _db_with_profile()
    writer = MagicMock()
    writer.run.return_value = _writer_result()

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        patch("job_agent.ui.app.get_writer_agent", return_value=writer),
        patch("builtins.open", mock_open(read_data=b"docx-bytes")),
    ):
        _run_writer(
            job_id="job-42",
            match_score_id="ms-99",
            matched_skills=[],
        )

    st_mock.success.assert_called_once()
    success_msg = st_mock.success.call_args.args[0]
    assert "Documents ready" in success_msg

    # Two downloads, one per artifact.
    assert st_mock.download_button.call_count == 2
    labels = [c.args[0] for c in st_mock.download_button.call_args_list]
    assert "Download cover letter" in labels
    assert "Download CV variant" in labels
    st_mock.error.assert_not_called()


def test_prepare_button_shows_error_on_failure() -> None:
    """If WriterAgent.run raises, st.error fires and no downloads appear."""
    db = _db_with_profile()
    writer = MagicMock()
    writer.run.side_effect = RuntimeError("gwdg down")

    with (
        _patched_streamlit() as st_mock,
        patch("job_agent.ui.app.get_db", return_value=db),
        patch("job_agent.ui.app.get_writer_agent", return_value=writer),
    ):
        _run_writer(
            job_id="job-42",
            match_score_id="ms-99",
            matched_skills=[],
        )

    st_mock.error.assert_called_once()
    assert "gwdg down" in st_mock.error.call_args.args[0]
    st_mock.success.assert_not_called()
    st_mock.download_button.assert_not_called()
