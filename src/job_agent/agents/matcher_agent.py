"""Matcher agent: retrieve top-N similar jobs via pgvector RPC, run LLM gap analysis."""

from __future__ import annotations

import json
import logging
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from contextvars import copy_context
from typing import TYPE_CHECKING, Any, NamedTuple, cast

if TYPE_CHECKING:
    from job_agent.tools.observability_store import ObservabilityStore

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from job_agent.agents.base_agent import JSON_ONLY_PREAMBLE, BaseAgent
from job_agent.config import get_settings
from job_agent.db.client import SupabaseClient
from job_agent.models.match import MatchResult, RankedJob
from job_agent.tools.llm_json import extract_first_json, strip_json_fences
from job_agent.tools.run_context import ProgressCb, StopCb
from job_agent.tools.run_context import emit_progress as _emit

logger = logging.getLogger(__name__)

_SCHEMA_HINT = """{
  "score": <int 0..100, how well the candidate matches>,
  "matched_skills": ["<skill candidate HAS that the job requires>", ...],
  "gaps": ["<skill the job requires that the candidate does NOT have>", ...],
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


class _ScoreOutcome(NamedTuple):
    """Result of scoring one job in a worker: a persistable row XOR an error."""

    row: dict[str, Any] | None
    error: str | None


class MatcherAgent:
    """Retrieves top-N candidate jobs via pgvector RPC, runs LLM gap analysis,
    and persists results to the match_scores table.
    """

    def __init__(
        self,
        db: SupabaseClient | None = None,
        llm_agent: BaseAgent | None = None,
        obs: ObservabilityStore | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        self._db = db if db is not None else SupabaseClient()
        self._llm = llm_agent if llm_agent is not None else BaseAgent(obs=obs)
        self._obs = obs
        self._max_concurrency = max_concurrency

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_candidate_text(profile_row: dict[str, Any] | None) -> str:
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
            "IMPORTANT: matched_skills must only contain skills that are explicitly "
            "present in the Candidate section — do NOT copy job requirements into "
            "matched_skills if the candidate does not have them. "
            "Skills the job requires but the candidate lacks belong in gaps. "
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

    def _score_one(
        self, candidate_text: str, job: RankedJob, user_id: str
    ) -> _ScoreOutcome:
        """Pure per-job worker: prompt -> LLM -> parse -> row. Returns an outcome;
        never mutates shared state (the driver aggregates on the main thread)."""
        prompt = self._build_prompt(candidate_text, job)
        try:
            result = self._llm.ask_with_provider(prompt)
        except Exception as exc:  # noqa: BLE001 — collected, not fatal
            return _ScoreOutcome(None, f"LLM call failed for job {job.job_id}: {exc}")

        cleaned = strip_json_fences(result.content)
        try:
            # extract_first_json tolerates trailing prose after the closing brace
            # (e.g. apertus-70b commentary) that plain json.loads rejects.
            data = extract_first_json(cleaned)
            match_result = MatchResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            return _ScoreOutcome(None, f"Parse/validation error for job {job.job_id}: {exc}")

        row = match_result.to_supabase_row(job.job_id)
        row["user_id"] = user_id
        row["model_provider"] = result.provider
        return _ScoreOutcome(row, None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        profile_id: str,
        *,
        user_id: str,
        top_n: int = 5,
        exclude_scored: bool = True,
        job_ids: list[str] | None = None,
        on_progress: ProgressCb | None = None,
        should_stop: StopCb | None = None,
    ) -> MatcherResult:
        """Fetch top-N jobs for *profile_id*, run LLM gap analysis, persist results.

        Scores are scoped to *user_id*: the RPC excludes jobs already scored by
        this user, and every persisted ``match_scores`` row is stamped with it.
        ``on_progress`` (optional) receives per-job progress dicts.
        When *job_ids* is non-empty, the pgvector RPC is skipped and those
        specific jobs are fetched from the ``jobs`` table instead.
        Wraps _do_run() with observability instrumentation.
        """
        from job_agent.tools.run_context import start_run
        ctx = start_run("matcher")
        if self._obs:
            self._obs.insert_run(ctx, user_id=user_id)
        try:
            result = self._do_run(
                profile_id, user_id, top_n, exclude_scored, on_progress,
                job_ids=job_ids, should_stop=should_stop,
            )
            if self._obs:
                self._obs.finish_run(ctx.run_id, "success")
            return result
        except Exception as exc:
            if self._obs:
                self._obs.finish_run(ctx.run_id, "error", str(exc)[:500])
            raise

    def _do_run(
        self,
        profile_id: str,
        user_id: str,
        top_n: int = 5,
        exclude_scored: bool = True,
        on_progress: ProgressCb | None = None,
        *,
        job_ids: list[str] | None = None,
        should_stop: StopCb | None = None,
    ) -> MatcherResult:
        """Fetch top-N jobs for *profile_id*, run LLM gap analysis, persist results.

        Returns a MatcherResult summary with counts and any per-row errors.
        When *job_ids* is non-empty, the pgvector RPC is skipped and those
        specific jobs are fetched from the ``jobs`` table instead.
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
        candidate_text = self.build_candidate_text(prof_data)

        # Step 1 — get jobs to score
        if job_ids:
            ids_to_score = list(job_ids)

            if exclude_scored:
                existing = (
                    self._db.raw.table("match_scores")
                    .select("job_id")
                    .eq("user_id", user_id)
                    .in_("job_id", ids_to_score)
                    .execute()
                    .data or []
                )
                already_scored = {cast("dict[str, Any]", r)["job_id"] for r in existing}
                ids_to_score = [jid for jid in ids_to_score if jid not in already_scored]

            if not ids_to_score:
                return MatcherResult(candidates_considered=0, scored=0, persisted=0, errors=[])

            raw_rows = (
                self._db.raw.table("jobs")
                .select("id, title, company, description, requirements")
                .in_("id", ids_to_score)
                .execute()
                .data or []
            )
            if not raw_rows:
                logger.warning(
                    "job_ids path: none of %d requested IDs found in jobs table",
                    len(ids_to_score),
                )
            rpc_rows: list[Any] = [
                {
                    "job_id": cast("dict[str, Any]", r)["id"],
                    "title": cast("dict[str, Any]", r).get("title", ""),
                    "company": cast("dict[str, Any]", r).get("company"),
                    "description": cast("dict[str, Any]", r).get("description"),
                    "requirements": cast("dict[str, Any]", r).get("requirements") or [],
                    "similarity": 0.0,
                }
                for r in raw_rows
            ]
        else:
            rpc_response = self._db.raw.rpc(
                "match_jobs_for_profile",
                {
                    "profile_id": profile_id,
                    "p_user_id": user_id,
                    "top_n": top_n,
                    "exclude_scored": exclude_scored,
                },
            ).execute()
            rpc_rows = cast(list[Any], rpc_response.data or [])

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
                    err = f"RPC row validation error: {exc}"
                    errors.append(err)
                    logger.warning("matcher %s", err)

        # Step 3 — LLM gap analysis per job, bounded-concurrent
        scored_rows: list[Any] = []
        total = len(ranked_jobs)
        _emit(on_progress, stage="start", total=total)

        cap = (
            self._max_concurrency
            if self._max_concurrency is not None
            else get_settings().matcher_max_concurrency
        )
        with ThreadPoolExecutor(max_workers=cap) as ex:
            # copy_context().run carries the run's ContextVar (_current_run) into
            # each worker so ask_with_provider's get_current_run() resolves and
            # llm_events get the real run_id. DO NOT simplify to
            # ex.submit(self._score_one, ...) — that orphans events as run_id="unknown".
            futures = [
                ex.submit(copy_context().run, self._score_one, candidate_text, job, user_id)
                for job in ranked_jobs
            ]
            resolved = 0
            stopping = False
            for fut in as_completed(futures):
                if should_stop is not None and not stopping and should_stop():
                    stopping = True
                    for f in futures:
                        f.cancel()  # cancels queued futures; in-flight ones finish
                try:
                    outcome = fut.result()
                except CancelledError:
                    continue
                resolved += 1
                if outcome.error is not None and len(errors) < _MAX_ERRORS:
                    errors.append(outcome.error)
                    logger.warning("matcher %s", outcome.error)
                if outcome.row is not None:
                    scored_rows.append(outcome.row)
                _emit(on_progress, stage="scoring", current=resolved, total=total)

        _emit(on_progress, stage="done", current=total, total=total)

        # Step 4 — batch upsert to match_scores
        persisted = 0
        if scored_rows:
            self._db.raw.table("match_scores").upsert(
                scored_rows, on_conflict="user_id,job_id"
            ).execute()
            persisted = len(scored_rows)

        return MatcherResult(
            candidates_considered=len(rpc_rows),
            scored=len(scored_rows),
            persisted=persisted,
            errors=errors[:_MAX_ERRORS],
        )
