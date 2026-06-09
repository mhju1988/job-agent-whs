"""Tests for MatchResult and RankedJob pydantic models."""

import pytest
from pydantic import ValidationError

from job_agent.models.match import MatchResult, RankedJob


def _valid_data(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "score": 75,
        "matched_skills": ["Python", "SQL"],
        "gaps": ["Kubernetes"],
        "rationale": "Good fit overall.",
    }
    base.update(overrides)
    return base


def test_match_result_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        MatchResult.model_validate({**_valid_data(), "unexpected_field": "boom"})


def test_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchResult.model_validate(_valid_data(score=101))


def test_score_lower_bound_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchResult.model_validate(_valid_data(score=-1))


def test_to_supabase_row_keys() -> None:
    result = MatchResult.model_validate(_valid_data())
    row = result.to_supabase_row("abc-123")
    assert set(row.keys()) == {"job_id", "score", "matched_skills", "gaps", "rationale"}


def test_to_supabase_row_score_is_float() -> None:
    result = MatchResult.model_validate(_valid_data(score=80))
    row = result.to_supabase_row("job-1")
    assert isinstance(row["score"], float)
    assert row["score"] == 80.0


def test_to_supabase_row_job_id() -> None:
    result = MatchResult.model_validate(_valid_data())
    row = result.to_supabase_row("my-job-id")
    assert row["job_id"] == "my-job-id"


# ---------------------------------------------------------------------------
# Spec-required tests
# ---------------------------------------------------------------------------


def test_match_result_round_trip() -> None:
    data = _valid_data()
    result = MatchResult.model_validate(data)
    assert result.score == 75
    assert result.matched_skills == ["Python", "SQL"]
    assert result.gaps == ["Kubernetes"]
    assert result.rationale == "Good fit overall."


def test_ranked_job_forbids_extra() -> None:
    with pytest.raises(ValidationError):
        RankedJob.model_validate(
            {
                "job_id": "abc",
                "title": "Engineer",
                "similarity": 0.9,
                "extra_field": "bad",
            }
        )


def test_ranked_job_round_trip() -> None:
    data = {
        "job_id": "job-001",
        "title": "Data Engineer",
        "company": "ACME",
        "description": "Build pipelines.",
        "requirements": ["Python", "Spark"],
        "similarity": 0.87,
    }
    job = RankedJob.model_validate(data)
    assert job.job_id == "job-001"
    assert job.similarity == 0.87
    assert job.match is None


def test_ranked_job_with_embedded_match() -> None:
    match = MatchResult(score=80, rationale="Good fit.")
    job = RankedJob(job_id="x", title="Dev", similarity=0.5, match=match)
    assert job.match is not None
    assert job.match.score == 80
