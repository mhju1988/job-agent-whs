"""Tests for job_agent.agents.writer_agent."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from job_agent.agents.writer_agent import WriterAgent, WriterResult

USER_ID = "00000000-0000-0000-0000-0000000000aa"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_profile_row() -> dict:
    return {
        "id": "profile-uuid",
        "summary": "Python developer with 5 years experience.",
        "skills": ["Python", "SQL", "Docker"],
        "highlighted_skills": [],
        "experience": [
            {
                "title": "Backend Engineer",
                "company": "TechCorp",
                "start": "2020-01",
                "end": "2024-01",
                "description": "Built REST APIs.",
            }
        ],
        "education": [
            {
                "degree": "B.Sc. Computer Science",
                "institution": "Example University",
                "field": "Computer Science",
                "start": "2016",
                "end": "2020",
            }
        ],
        "languages": ["English"],
    }


def _make_job_row() -> dict:
    return {
        "source": "arbeitsagentur",
        "external_id": "ext-001",
        "url": "https://example.com/job/1",
        "title": "Python Developer",
        "company": "Acme GmbH",
        "location": "Berlin",
        "requirements": ["Python", "SQL"],
        "description": "We need a Python dev.",
        "scraped_at": "2024-01-01T00:00:00Z",
    }


def _make_match_row() -> dict:
    return {
        "id": "match-uuid",
        "score": 80,
        "matched_skills": [],  # empty simulates pre-migration row; caller's list is used
        "gaps": ["AWS"],
        "rationale": "Good fit overall.",
    }


def _make_db_mock(
    profile_row: dict | None = None,
    job_row: dict | None = None,
    match_row: dict | None = None,
    application_id: str = "app-uuid-123",
) -> MagicMock:
    """Build a mock SupabaseClient whose .raw chain returns the given rows.

    Caches one MagicMock per table name so assertions done *after* agent.run()
    reference the same objects the agent used.
    """
    db = MagicMock()

    def _select_mock(data: list) -> MagicMock:
        t = MagicMock()
        # Single-eq chain (profile, jobs)
        t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = data
        # Double-eq chain (match_scores: .eq("id",...).eq("job_id",...))
        double_eq = t.select.return_value.eq.return_value.eq.return_value
        double_eq.limit.return_value.execute.return_value.data = data
        return t

    # Build stable per-table mocks
    profile_mock = _select_mock([profile_row] if profile_row is not None else [])
    job_mock = _select_mock([job_row] if job_row is not None else [])
    match_mock = _select_mock([match_row] if match_row is not None else [])

    app_mock = MagicMock()
    app_mock.upsert.return_value.execute.return_value.data = [{"id": application_id}]

    table_map: dict[str, MagicMock] = {
        "profile": profile_mock,
        "jobs": job_mock,
        "match_scores": match_mock,
        "applications": app_mock,
    }

    raw = MagicMock()
    raw.table.side_effect = lambda name: table_map.get(name, MagicMock())
    db.raw = raw
    # Expose app_mock so tests can assert on it directly
    db._app_mock = app_mock
    return db


_DEFAULT_LETTER = "Dear Hiring Manager,\n\nSincerely,\nCandidate"


def _make_renderer_mock(letter_text: str = _DEFAULT_LETTER) -> MagicMock:
    renderer = MagicMock()
    renderer.render.return_value = letter_text
    return renderer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_end_to_end_writes_both_docx_and_updates_application(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=_make_job_row(),
        match_row=_make_match_row(),
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    result = agent.run(
        profile_id="profile-uuid",
        job_id="job-uuid",
        match_score_id="match-uuid",
        candidate_name="John Doe",
        matched_skills=["Python", "SQL"],
        user_id=USER_ID,
    )

    # Both files exist
    assert Path(result.cover_letter_path).exists()
    assert Path(result.cv_variant_path).exists()

    # Renderer called once with correct args
    renderer.render.assert_called_once()
    call_kwargs = renderer.render.call_args.kwargs
    assert call_kwargs["candidate_name"] == "John Doe"
    assert call_kwargs["matched_skills"] == ["Python", "SQL"]
    assert call_kwargs["gaps_addressed"] == ["AWS"]

    # Upsert called with required fields + status + on_conflict kwarg
    db._app_mock.upsert.assert_called_once()
    upsert_call = db._app_mock.upsert.call_args
    upserted_row = upsert_call.args[0]
    assert upserted_row["status"] == "ready_to_send"
    assert upserted_row["job_id"] == "job-uuid"
    assert upserted_row["user_id"] == USER_ID
    # on_conflict is (user_id, job_id) so two users can apply to the same job
    # without colliding (migration 011 swapped the old UNIQUE(job_id)).
    assert upsert_call.kwargs.get("on_conflict") == "user_id,job_id"
    # All snapshot fields populated so the application survives the jobs purge.
    for snap in ("job_title", "job_company", "job_url", "job_source"):
        assert snap in upserted_row


def test_returns_writer_result_with_paths(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=_make_job_row(),
        match_row=_make_match_row(),
        application_id="app-abc",
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    result = agent.run(
        profile_id="p1",
        job_id="j1",
        match_score_id="m1",
        candidate_name="Jane Smith",
        matched_skills=["Python"],
        user_id=USER_ID,
    )

    assert isinstance(result, WriterResult)
    assert result.application_id == "app-abc"
    # Paths must be absolute strings
    assert Path(result.cover_letter_path).is_absolute()
    assert Path(result.cv_variant_path).is_absolute()
    # Files actually exist
    assert Path(result.cover_letter_path).exists()
    assert Path(result.cv_variant_path).exists()


def test_status_set_to_ready_to_send(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=_make_job_row(),
        match_row=_make_match_row(),
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    result = agent.run(
        profile_id="p1",
        job_id="j1",
        match_score_id="m1",
        candidate_name="Test",
        matched_skills=[],
        user_id=USER_ID,
    )

    assert result.status == "ready_to_send"

    upserted_row = db._app_mock.upsert.call_args[0][0]
    assert upserted_row["status"] == "ready_to_send"


def test_slug_strips_special_chars(tmp_path: Path) -> None:
    """Filenames from special-char titles/companies: alnum+dash only, lowercase, max 40 chars."""
    job_row = _make_job_row()
    job_row["title"] = "Senior Dev (m/w/d) — Berlin!"
    job_row["company"] = "Acme GmbH & Co. KG"

    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=job_row,
        match_row=_make_match_row(),
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    result = agent.run(
        profile_id="p1",
        job_id="j1",
        match_score_id="m1",
        candidate_name="Test",
        matched_skills=[],
        user_id=USER_ID,
    )

    cover_name = Path(result.cover_letter_path).name
    cv_name = Path(result.cv_variant_path).name

    # Strip prefix and suffix (.docx) to get the slug parts
    # cover_letter_{user_prefix}_{company}_{title}.docx
    cover_stem = cover_name.removeprefix("cover_letter_").removesuffix(".docx")
    cv_stem = cv_name.removeprefix("cv_").removesuffix(".docx")

    # Stem is "{user_prefix}_{company_slug}_{title_slug}" — three parts.
    alnum_dash_re = re.compile(r"^[a-z0-9-]+$")
    cover_parts = cover_stem.split("_", 2)
    cv_parts = cv_stem.split("_", 2)

    assert len(cover_parts) == 3, f"expected user_company_title in stem: {cover_stem!r}"
    user_part, company_part, title_part = cover_parts
    assert re.match(r"^[0-9a-f]{8}$", user_part), f"user prefix invalid: {user_part!r}"
    assert alnum_dash_re.match(company_part), f"company slug invalid: {company_part!r}"
    assert alnum_dash_re.match(title_part), f"title slug invalid: {title_part!r}"
    assert len(company_part) <= 40
    assert len(title_part) <= 40

    # Same checks on cv stem
    assert len(cv_parts) == 3
    assert re.match(r"^[0-9a-f]{8}$", cv_parts[0])
    assert alnum_dash_re.match(cv_parts[1])
    assert alnum_dash_re.match(cv_parts[2])


def test_missing_profile_raises(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=None,  # no profile
        job_row=_make_job_row(),
        match_row=_make_match_row(),
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    with pytest.raises(LookupError, match="profile"):
        agent.run(
            profile_id="nonexistent",
            job_id="j1",
            match_score_id="m1",
            candidate_name="Test",
            matched_skills=[],
            user_id=USER_ID,
        )


def test_missing_match_raises(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=_make_job_row(),
        match_row=None,  # no match
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    with pytest.raises(LookupError, match="match_score"):
        agent.run(
            profile_id="p1",
            job_id="j1",
            match_score_id="nonexistent",
            candidate_name="Test",
            matched_skills=[],
            user_id=USER_ID,
        )


def test_missing_job_raises(tmp_path: Path) -> None:
    db = _make_db_mock(
        profile_row=_make_profile_row(),
        job_row=None,  # no job
        match_row=_make_match_row(),
    )
    renderer = _make_renderer_mock()

    agent = WriterAgent(db=db, renderer=renderer, artifacts_dir=tmp_path)
    with pytest.raises(LookupError, match="job"):
        agent.run(
            profile_id="p1",
            job_id="nonexistent",
            match_score_id="m1",
            candidate_name="Test",
            matched_skills=[],
            user_id=USER_ID,
        )
