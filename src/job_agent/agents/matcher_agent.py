"""Matcher agent: retrieve top-N similar jobs via pgvector RPC, run LLM gap analysis."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from job_agent.agents.base_agent import JSON_ONLY_PREAMBLE, BaseAgent
from job_agent.db.client import SupabaseClient
from job_agent.models.match import MatchResult, RankedJob
from job_agent.tools.llm_json import strip_json_fences

logger = logging.getLogger(__name__)

_SCHEMA_HINT = """{
  "score": <int 0..100, how well the candidate matches>,
  "matched_skills": ["<string>", ...],
  "gaps": ["<string>", ...],
  "rationale": "<one paragraph explaining the score>"
}"""

# Worked example calibrating the model's scoring scale.
_FEW_SHOT_EXAMPLE = """Example:
Candidate:
Skills: Python, SQL, REST APIs, Git, Docker
Summary: 5 years building Python backends.
Job:
Title: Python Backend Developer
Company: FooCorp
Requirements: Python, PostgreSQL, FastAPI, AWS
Description: Build and operate REST APIs on AWS.
Expected output:
{"score": 75, "matched_skills": ["Python", "REST APIs", "SQL"], "gaps": ["AWS", "FastAPI"], "rationale": "Strong Python and REST background, with relational DB experience that maps to PostgreSQL. AWS and FastAPI are missing but both are acquirable on the job."}
"""  # noqa: E501

_MAX_ERRORS = 10


class MatcherResult(BaseModel):
    """Summary returned by MatcherAgent.run()."""

    model_config = ConfigDict(extra="forbid")

    candidates_considered: int
    scored: int
    persisted: int
    errors: list[str] = Field(default_factory=list)


class MatcherAgent:
    """Retrieves top-N candidate jobs via pgvector RPC, runs LLM gap analysis,
    and persists results to the match_scores table.
    """

    def __init__(
        self,
        db: SupabaseClient | None = None,
        llm_agent: BaseAgent | None = None,
    ) -> None:
        self._db = db if db is not None else SupabaseClient()
        self._llm = llm_agent if llm_agent is not None else BaseAgent()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_candidate_text(profile_row: dict[str, Any] | None) -> str:
        """Compact candidate brief assembled from a `profile` table row."""
        if not profile_row:
            return "(no candidate profile available)"
        parts: list[str] = []
        if summary := profile_row.get("summary"):
            parts.append(f"Summary: {summary}")
        skills = profile_row.get("skills") or []
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")
        for exp in (profile_row.get("experience") or [])[:3]:
            line = f"{exp.get('title', '?')} at {exp.get('company', '?')}"
            if desc := exp.get("description"):
                line += f" — {desc}"
            parts.append(line)
        for edu in (profile_row.get("education") or [])[:2]:
            parts.append(f"{edu.get('degree', '?')} at {edu.get('institution', '?')}")
        languages = profile_row.get("languages") or []
        if languages:
            parts.append(f"Languages: {', '.join(languages)}")
        return "\n".join(parts) if parts else "(empty profile)"

    @staticmethod
    def _build_prompt(candidate_text: str, job: RankedJob) -> str:
        requirements_text = ", ".join(job.requirements) if job.requirements else "n/a"
        return (
            f"{JSON_ONLY_PREAMBLE}"
            "Compare the candidate against the job below and score the match. "
            "Return a JSON object matching the schema. Use the example as a "
            "calibration reference for how to score and what to extract.\n\n"
            f"Schema:\n{_SCHEMA_HINT}\n\n"
            f"{_FEW_SHOT_EXAMPLE}\n"
            "Now score this pair:\n\n"
            f"Candidate:\n{candidate_text}\n\n"
            f"Job:\n"
            f"Title: {job.title}\n"
            f"Company: {job.company or 'n/a'}\n"
            f"Requirements: {requirements_text}\n"
            f"Description: {job.description or 'n/a'}\n"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        profile_id: str,
        top_n: int = 5,
        exclude_scored: bool = True,
    ) -> MatcherResult:
        """Fetch top-N jobs for *profile_id*, run LLM gap analysis, persist results.

        Returns a MatcherResult summary with counts and any per-row errors.
        """
        # Step 0 — fetch the candidate profile once (used in every prompt).
        prof_resp = (
            self._db.raw.table("profile")
            .select("summary, skills, experience, education, languages")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        prof_raw = prof_resp.data[0] if (prof_resp.data and len(prof_resp.data) > 0) else None
        prof_data = cast("dict[str, Any] | None", prof_raw)
        candidate_text = self._build_candidate_text(prof_data)

        # Step 1 — call Supabase RPC
        rpc_response = self._db.raw.rpc(
            "match_jobs_for_profile",
            {
                "profile_id": profile_id,
                "top_n": top_n,
                "exclude_scored": exclude_scored,
            },
        ).execute()

        rpc_rows: list[Any] = cast(list[Any], rpc_response.data or [])

        if not rpc_rows:
            return MatcherResult(
                candidates_considered=0,
                scored=0,
                persisted=0,
                errors=[],
            )

        # Step 2 — parse RPC rows into RankedJob objects
        ranked_jobs: list[RankedJob] = []
        errors: list[str] = []

        for row in rpc_rows:
            try:
                ranked_jobs.append(RankedJob.model_validate(row))
            except ValidationError as exc:
                if len(errors) < _MAX_ERRORS:
                    errors.append(f"RPC row validation error: {exc}")

        # Step 3 — LLM gap analysis per job
        scored_rows: list[Any] = []

        for job in ranked_jobs:
            prompt = self._build_prompt(candidate_text, job)
            try:
                raw = self._llm.ask(prompt)
            except Exception as exc:
                if len(errors) < _MAX_ERRORS:
                    errors.append(f"LLM call failed for job {job.job_id}: {exc}")
                continue

            cleaned = strip_json_fences(raw)

            try:
                # strict=False tolerates literal control characters (raw
                # newlines) inside string values — LLMs emit these in German
                # rationale prose instead of escaped "\n".
                data = json.loads(cleaned, strict=False)
                match_result = MatchResult.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                if len(errors) < _MAX_ERRORS:
                    errors.append(f"Parse/validation error for job {job.job_id}: {exc}")
                continue

            scored_rows.append(match_result.to_supabase_row(job.job_id))

        # Step 4 — batch upsert to match_scores
        persisted = 0
        if scored_rows:
            self._db.raw.table("match_scores").insert(scored_rows).execute()
            persisted = len(scored_rows)

        return MatcherResult(
            candidates_considered=len(rpc_rows),
            scored=len(scored_rows),
            persisted=persisted,
            errors=errors[:_MAX_ERRORS],
        )
