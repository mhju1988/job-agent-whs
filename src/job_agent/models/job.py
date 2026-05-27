"""Pydantic v2 Job model — mirrors the `jobs` table in 001_init.sql."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["arbeitsagentur", "adzuna", "jsearch"]
    external_id: str
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    requirements: list[str] = Field(default_factory=list)
    description: str | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_supabase_row(self) -> dict[str, Any]:
        """Return a dict suitable for client.raw.table("jobs").upsert(...)."""
        return {
            "source": self.source,
            "external_id": self.external_id,
            "url": self.url,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "requirements": self.requirements,
            "description": self.description,
            "scraped_at": self.scraped_at.isoformat().replace("+00:00", "Z"),
        }
