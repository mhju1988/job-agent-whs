"""Pydantic model for LLM-generated cover letter content."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoverLetterContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening: str  # 1-2 sentences greeting + hook
    body: str     # 1-2 short paragraphs of substance
    closing: str  # 1 sentence sign-off
