"""Tests for the CV-upload sidebar feature in job_agent.ui.app."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from job_agent.models.profile import Profile
from job_agent.tools.cv_parser import CVParseError, CVParser
from job_agent.tools.embedder import EmbeddingServiceError
from job_agent.ui.app import handle_cv_upload

# ---------------------------------------------------------------------------
# CVParser.parse_bytes
# ---------------------------------------------------------------------------


def _fake_pdf_reader_factory() -> object:
    """A pdf_reader_factory that returns one page with non-empty text."""

    class _Page:
        def extract_text(self) -> str:
            return "name: Jane Doe\nskills: Python, SQL\n"

    class _Reader:
        pages = [_Page()]

        def __init__(self, _path: object) -> None:
            pass

    return _Reader


def test_parse_bytes_roundtrip() -> None:
    """parse_bytes writes a tmp file, delegates to parse(), and cleans up."""
    llm = MagicMock()
    llm.ask.return_value = (
        '{"summary": "Engineer", "skills": ["Python", "SQL"], '
        '"experience": [], "education": [], "languages": []}'
    )
    parser = CVParser(
        llm_agent=llm,
        pdf_reader_factory=_fake_pdf_reader_factory(),  # type: ignore[arg-type]
    )

    # Any non-empty bytes will do — the fake reader ignores the path content.
    result = parser.parse_bytes(b"%PDF-1.4 fake bytes")

    assert isinstance(result, Profile)
    assert result.skills == ["Python", "SQL"]
    assert result.summary == "Engineer"
    llm.ask.assert_called_once()


def test_parse_drops_incomplete_education_entry() -> None:
    """Education entries with null/empty required fields are silently dropped."""
    llm = MagicMock()
    llm.ask.return_value = (
        '{"summary": "S", "skills": ["Python"], "experience": [],'
        ' "education": ['
        '   {"degree": "B.Sc.", "institution": "TU Berlin"},'
        '   {"degree": null,    "institution": "Some Bootcamp"},'
        '   {"degree": "M.Sc.", "institution": "  "}'
        ' ],'
        ' "languages": []}'
    )
    parser = CVParser(
        llm_agent=llm,
        pdf_reader_factory=_fake_pdf_reader_factory(),  # type: ignore[arg-type]
    )

    profile = parser.parse_bytes(b"%PDF...")

    # Only the first entry survives sanitisation.
    assert len(profile.education) == 1
    assert profile.education[0].degree == "B.Sc."
    assert profile.education[0].institution == "TU Berlin"


def test_parse_bytes_empty_raises() -> None:
    """An empty upload short-circuits to a clear error."""
    parser = CVParser(llm_agent=MagicMock())
    with pytest.raises(CVParseError, match="empty"):
        parser.parse_bytes(b"")


# ---------------------------------------------------------------------------
# handle_cv_upload — success and failure paths
# ---------------------------------------------------------------------------


def _make_db_mock() -> MagicMock:
    """Build a db whose profile table chain supports both delete().neq() and insert()."""
    db = MagicMock()
    table_mock = MagicMock()
    table_mock.delete.return_value.neq.return_value.execute.return_value.data = []
    table_mock.insert.return_value.execute.return_value.data = [{"id": "profile-uuid"}]
    db.raw.table.return_value = table_mock
    db._table_mock = table_mock
    return db


def test_upload_widget_success() -> None:
    """Happy path: parser + embedder + delete + insert all succeed → st.success."""
    profile = Profile(summary="x", skills=["Python"])
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = profile
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024
    db = _make_db_mock()

    # Stub run_matcher so the new auto-rescore path doesn't hit the
    # real MatcherAgent (tested separately in test_cv_upload_matcher.py).
    with (
        patch("job_agent.ui.app.st") as st_mock,
        patch("job_agent.ui.app.run_matcher", return_value=None),
    ):
        ok = handle_cv_upload(b"%PDF...", db, parser=parser, embedder=embedder)

    assert ok is True
    # Two success calls now: "Profile updated." + the auto-rescore feedback;
    # with run_matcher stubbed to None, the second is a warning instead.
    assert st_mock.success.call_count >= 1
    st_mock.error.assert_not_called()
    # Delete-then-insert pattern was used.
    db._table_mock.delete.assert_called_once()
    insert_call = db._table_mock.insert.call_args
    inserted_row = insert_call.args[0]
    assert inserted_row["skills"] == ["Python"]
    assert inserted_row["embedding"] == [0.0] * 1024


def test_upload_widget_cv_parse_error() -> None:
    """CVParseError → st.error called, no DB write attempted, returns False."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.side_effect = CVParseError("bad pdf")
    embedder = MagicMock()
    db = _make_db_mock()

    with patch("job_agent.ui.app.st") as st_mock:
        ok = handle_cv_upload(b"x", db, parser=parser, embedder=embedder)

    assert ok is False
    st_mock.error.assert_called_once()
    assert "bad pdf" in st_mock.error.call_args.args[0]
    st_mock.success.assert_not_called()
    db._table_mock.delete.assert_not_called()
    db._table_mock.insert.assert_not_called()


def test_upload_widget_embedding_error() -> None:
    """EmbeddingServiceError → st.error, no DB write, returns False."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = Profile(skills=["Python"])
    embedder = MagicMock()
    embedder.embed_text.side_effect = EmbeddingServiceError("gwdg down")
    db = _make_db_mock()

    with patch("job_agent.ui.app.st") as st_mock:
        ok = handle_cv_upload(b"x", db, parser=parser, embedder=embedder)

    assert ok is False
    st_mock.error.assert_called_once()
    assert "gwdg down" in st_mock.error.call_args.args[0]
    db._table_mock.delete.assert_not_called()
    db._table_mock.insert.assert_not_called()


def test_upload_widget_insert_failure() -> None:
    """Supabase insert failure surfaces via the outer-fallback st.error."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.return_value = Profile(skills=["Python"])
    embedder = MagicMock()
    embedder.embed_text.return_value = [0.0] * 1024
    db = _make_db_mock()
    db._table_mock.insert.return_value.execute.side_effect = RuntimeError(
        "constraint violated"
    )

    with patch("job_agent.ui.app.st") as st_mock:
        ok = handle_cv_upload(b"x", db, parser=parser, embedder=embedder)

    assert ok is False
    st_mock.error.assert_called_once()
    assert "constraint violated" in st_mock.error.call_args.args[0]


def test_upload_widget_outer_exception_fallback() -> None:
    """Any unwrapped exception (e.g. raw OSError from pypdf) is caught."""
    parser = MagicMock(spec=CVParser)
    parser.parse_bytes.side_effect = OSError("disk full")  # not CVParseError
    embedder = MagicMock()
    db = _make_db_mock()

    with patch("job_agent.ui.app.st") as st_mock:
        ok = handle_cv_upload(b"x", db, parser=parser, embedder=embedder)

    assert ok is False
    st_mock.error.assert_called_once()
    assert "disk full" in st_mock.error.call_args.args[0]


# ---------------------------------------------------------------------------
# _profile_label — full_name driven
# ---------------------------------------------------------------------------


def _db_with_profile_row(row: dict | None) -> MagicMock:
    """Mock db whose profile.select('full_name, skills').limit(1).execute() returns row(s)."""
    db = MagicMock()
    db.raw.table.return_value.select.return_value.limit.return_value.execute.return_value.data = (
        [row] if row is not None else []
    )
    return db


def test_profile_label_shows_full_name() -> None:
    from job_agent.ui.app import _profile_label

    db = _db_with_profile_row({"full_name": "Max Mustermann", "skills": ["Python", "SQL"]})
    assert _profile_label(db) == "Max Mustermann · 2 skills"


def test_profile_label_fallback_when_no_name() -> None:
    from job_agent.ui.app import _profile_label

    db = _db_with_profile_row({"full_name": None, "skills": ["Python"]})
    assert _profile_label(db) == "Unnamed · 1 skills"


def test_profile_label_no_profile() -> None:
    from job_agent.ui.app import _profile_label

    db = _db_with_profile_row(None)
    assert _profile_label(db) == "No profile uploaded yet"


def test_profile_label_db_error_returns_safe_string() -> None:
    """Sidebar must never crash — any DB exception → human-readable fallback."""
    from job_agent.ui.app import _profile_label

    db = MagicMock()
    db.raw.table.side_effect = RuntimeError("connection refused")
    assert _profile_label(db) == "Profile (could not load)"
