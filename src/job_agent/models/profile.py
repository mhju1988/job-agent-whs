"""Pydantic v2 Profile model — mirrors the `profile` table in Supabase."""

from __future__ import annotations

# `Any` is justified here because `to_supabase_row()` returns genuinely mixed
# value types (str, list[str], list[dict], None) destined for a Supabase row;
# a tighter union would not add safety.
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    company: str
    start: str | None = None
    end: str | None = None
    description: str | None = None


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degree: str
    institution: str
    field: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Most human-identifiable field; deliberately excluded from
    # to_embedding_text() so names cannot bias semantic similarity.
    full_name: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    highlighted_skills: list[str] = Field(
        default_factory=list,
        description="Skills to surface first on the CV variant; must be a subset of `skills`.",
    )
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    def to_supabase_row(self) -> dict[str, Any]:
        """Return a dict suitable for upserting into the `profile` table."""
        return {
            "full_name": self.full_name,
            "summary": self.summary,
            "skills": self.skills,
            "experience": [exp.model_dump() for exp in self.experience],
            "education": [edu.model_dump() for edu in self.education],
            "languages": self.languages,
        }

    def to_embedding_text(self) -> str:
        """Produce a compact text representation for embedding."""
        parts: list[str] = []

        if self.summary:
            parts.append(self.summary)

        if self.skills:
            parts.append(", ".join(self.skills))

        for exp in self.experience:
            date_range = f"{exp.start or '?'}–{exp.end or 'present'}"
            line = f"{exp.title} at {exp.company} ({date_range})"
            if exp.description:
                line += f": {exp.description}"
            parts.append(line)

        for edu in self.education:
            line = edu.degree
            if edu.field:
                line += f" in {edu.field}"
            line += f" at {edu.institution}"
            if edu.start or edu.end:
                line += f" ({edu.start or '?'}–{edu.end or 'present'})"
            if edu.description:
                line += f": {edu.description}"
            parts.append(line)

        if self.languages:
            parts.append(", ".join(self.languages))

        return "\n".join(parts)
