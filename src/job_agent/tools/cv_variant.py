"""Pure-Python helper that builds a CV variant by highlighting matched skills.

No LLM call, no I/O. Safe to call in tight loops.
"""

from __future__ import annotations

from job_agent.models.match import MatchResult
from job_agent.models.profile import Profile


class CVVariantError(ValueError):
    """Raised when CV-variant generation would violate the no-invented-skills rule."""


def build_cv_variant(profile: Profile, match: MatchResult) -> Profile:
    """Return a new Profile with `highlighted_skills` populated.

    Reorders `skills` so that matches surface first; the original list is preserved.
    Hard rule: ``set(output.highlighted_skills) <= set(profile.skills)``. Any skill
    in ``match.matched_skills`` that is not in ``profile.skills`` is silently dropped
    (case-insensitive comparison); if doing so leaves the highlighted list empty
    while ``match.matched_skills`` was non-empty, no error is raised — that is a
    legitimate "no overlap" outcome.

    Defence in depth: at the end, assert the subset rule and raise ``CVVariantError``
    if violated (would only fire on a programming bug in this function).
    """
    # Build a lookup from lowercase → original-casing profile skill.
    # Assumes profile.skills has no case-only duplicates; last one wins if it does.
    lower_to_original: dict[str, str] = {s.lower(): s for s in profile.skills}

    # First-occurrence dedupe: keep the order from match.matched_skills, drop repeats.
    highlighted: list[str] = []
    seen: set[str] = set()
    for ms in match.matched_skills:
        original = lower_to_original.get(ms.lower())
        if original is not None and original not in seen:
            highlighted.append(original)
            seen.add(original)

    # Defence-in-depth: verify the subset rule before returning.
    profile_skills_set = set(profile.skills)
    if not set(highlighted) <= profile_skills_set:
        raise CVVariantError(
            f"highlighted_skills {highlighted!r} contains skills not in profile.skills "
            f"{profile.skills!r} — this is a bug in build_cv_variant."
        )

    return profile.model_copy(update={"highlighted_skills": highlighted})
