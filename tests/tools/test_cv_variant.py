"""Tests for tools/cv_variant.py — all hermetic, no LLM/I-O mocks needed."""

from __future__ import annotations

from job_agent.models.match import MatchResult
from job_agent.models.profile import Profile
from job_agent.tools.cv_variant import build_cv_variant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(skills: list[str]) -> Profile:
    return Profile(skills=skills)


def _match(matched: list[str]) -> MatchResult:
    return MatchResult(score=80, matched_skills=matched, gaps=[], rationale="ok")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_subset_rule_enforced() -> None:
    """Happy path: highlighted must be a strict subset of profile.skills."""
    profile = _profile(["Python", "SQL", "Docker"])
    match = _match(["Python", "SQL"])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == ["Python", "SQL"]
    assert set(out.highlighted_skills) <= set(profile.skills)


def test_original_skills_unchanged() -> None:
    """The original skills list must be preserved verbatim."""
    profile = _profile(["Python", "SQL", "Docker"])
    match = _match(["Python", "SQL"])
    out = build_cv_variant(profile, match)

    assert out.skills == profile.skills


def test_matched_first_order_preserved() -> None:
    """Order from match.matched_skills is preserved, not profile order."""
    profile = _profile(["Python", "SQL", "Docker"])
    match = _match(["SQL", "Python"])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == ["SQL", "Python"]


def test_empty_matched_returns_empty_highlighted() -> None:
    """Empty match.matched_skills → empty highlighted, no reordering."""
    profile = _profile(["Python", "SQL"])
    match = _match([])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == []
    assert out.skills == profile.skills


def test_invented_skill_silently_dropped() -> None:
    """Skills absent from profile are silently dropped; subset rule holds."""
    profile = _profile(["Python"])
    match = _match(["Python", "Rust"])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == ["Python"]
    assert set(out.highlighted_skills) <= set(profile.skills)


def test_case_insensitive_match() -> None:
    """Match is case-insensitive; original casing from profile is preserved."""
    profile = _profile(["PostgreSQL"])
    match = _match(["postgresql"])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == ["PostgreSQL"]


def test_returns_new_instance() -> None:
    """build_cv_variant must return a new Profile, not mutate the original."""
    profile = _profile(["Python"])
    match = _match(["Python"])
    out = build_cv_variant(profile, match)

    assert out is not profile


def test_duplicate_matched_skills_deduped_first_wins() -> None:
    """match.matched_skills with duplicates must dedupe; first occurrence wins."""
    profile = _profile(["Python", "SQL"])
    match = _match(["Python", "SQL", "python", "Python"])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == ["Python", "SQL"]


def test_no_skills_in_either_is_fine() -> None:
    """Both lists empty — no error, both output lists empty."""
    profile = _profile([])
    match = _match([])
    out = build_cv_variant(profile, match)

    assert out.highlighted_skills == []
    assert out.skills == []


def test_highlighted_skills_not_in_supabase_row() -> None:
    """highlighted_skills must not appear in the Supabase persistence row."""
    profile = Profile(skills=["X"], highlighted_skills=["X"])
    row = profile.to_supabase_row()

    assert "highlighted_skills" not in row


def test_highlighted_skills_not_in_embedding_text() -> None:
    """highlighted_skills must not affect embedding text (would skew vectors)."""
    # Use a skill that is NOT in regular skills so we can distinguish.
    profile = Profile(skills=[], highlighted_skills=["UniqueHighlightedSkill"])
    text = profile.to_embedding_text()

    assert "UniqueHighlightedSkill" not in text
