"""API request/response schemas (Pydantic v2, strict)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(_S):
    status: str = "ok"


class MeResponse(_S):
    user_id: str
    profile_label: str
    has_profile: bool
    scout_sources: list[str]


class ScoutRunRequest(_S):
    keyword: str | None = None
    location: str | None = None
    max_results: int = 10
    sources: list[str] | None = None


class MatcherRunRequest(_S):
    job_ids: list[str] = Field(default_factory=list, max_length=50)


class RescoreRunRequest(_S):
    limit: int = Field(ge=1)


class ProfileUpdateRequest(_S):
    skills: list[str] | None = None
    summary: str | None = Field(default=None, max_length=5000)

    @field_validator("skills")
    @classmethod
    def _normalize_skills(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for s in v:
            s2 = s.strip()
            if s2 and s2 not in seen:
                seen.add(s2)
                out.append(s2)
        return out

    @model_validator(mode="after")
    def _at_least_one(self) -> ProfileUpdateRequest:
        if self.skills is None and self.summary is None:
            raise ValueError("provide at least one of: skills, summary")
        return self


class WriterRunRequest(_S):
    job_id: str
    match_score_id: str
    matched_skills: list[str] = []
    candidate_name: str = "Max Mustermann"
    language: Literal["en", "de"] = "en"


class TransitionRequest(_S):
    target: str


class DeleteSummaryResponse(_S):
    profiles_deleted: int
    matches_deleted: int
    applications_deleted: int
    files_deleted: int
    obs_runs_deleted: int = 0


class HideJobsRequest(_S):
    job_ids: list[str] = Field(default_factory=list, max_length=200)


class DeleteApplicationsRequest(_S):
    application_ids: list[str] = Field(default_factory=list, max_length=200)


class DeleteApplicationsResponse(_S):
    deleted: int
    files_deleted: int


class AdminUserResponse(_S):
    id: str
    email: str | None
    created_at: str
    email_confirmed: bool
    banned: bool
    role: str


class AdminRoleRequest(_S):
    role: Literal["user", "admin"]


class AdminActionResponse(_S):
    ok: bool = True
