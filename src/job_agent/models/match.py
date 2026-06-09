"""Pydantic models for LLM-emitted gap analysis results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MatchResult(BaseModel):
    """LLM-emitted gap analysis for a single (profile, job) pair."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(..., ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    rationale: str

    def to_supabase_row(self, job_id: str) -> dict[str, object]:
        """Return a dict suitable for inserting into the `match_scores` table.

        Maps to columns: job_id, score, matched_skills, gaps, rationale.
        `score` is cast to float because the DB column is double precision.
        `matched_skills` requires migration 008 to be applied.
        """
        return {
            "job_id": job_id,
            "score": float(self.score),
            "matched_skills": self.matched_skills,
            "gaps": self.gaps,
            "rationale": self.rationale,
        }


class RankedJob(BaseModel):
    """One row from the match_jobs_for_profile RPC, optionally enriched with LLM analysis."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    title: str
    company: str | None = None
    description: str | None = None
    requirements: list[str] = Field(default_factory=list)
    similarity: float  # 0..1 from pgvector
    match: MatchResult | None = None  # populated after LLM gap analysis
