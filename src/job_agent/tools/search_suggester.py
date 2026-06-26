"""LLM-derived job-search suggestions from a candidate profile.

Given a compact candidate brief, proposes the most relevant role/title search
queries a job board would understand. Used to replace hardcoded search terms
with AI-determined ones (and to offer the user a pick-list).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, ValidationError

from job_agent.agents.base_agent import JSON_ONLY_PREAMBLE, BaseAgent
from job_agent.tools.llm_json import extract_first_json, strip_json_fences

if TYPE_CHECKING:
    from job_agent.tools.observability_store import ObservabilityStore

logger = logging.getLogger(__name__)

_SCHEMA_HINT = (
    '[{"keyword": "<role/title to search, e.g. Backend Python Developer>", '
    '"location": "<city or null>", "rationale": "<one short sentence>"}, ...]'
)


class SearchSuggestion(BaseModel):
    """A single AI-proposed job-search query."""

    model_config = ConfigDict(extra="forbid")

    keyword: str
    location: str | None = None
    rationale: str | None = None


class SearchSuggester:
    """Proposes job-search queries from a candidate brief via the GWDG LLM."""

    def __init__(
        self,
        llm_agent: BaseAgent | None = None,
        obs: ObservabilityStore | None = None,
    ) -> None:
        self._llm = llm_agent if llm_agent is not None else BaseAgent(obs=obs)

    @staticmethod
    def _build_prompt(candidate_text: str, max_suggestions: int) -> str:
        return (
            f"{JSON_ONLY_PREAMBLE}"
            f"Based on the candidate below, propose up to {max_suggestions} job-search "
            "queries — concrete role/title keywords a job board understands — that best "
            "match their skills, experience, and qualifications. Order by relevance, most "
            "relevant first. Prefer specific role titles over broad terms. Only include a "
            "location if the candidate's history clearly implies one; otherwise null. "
            "Return a JSON array matching the schema.\n\n"
            f"Schema:\n{_SCHEMA_HINT}\n\n"
            f"Candidate:\n{candidate_text}\n"
        )

    def suggest(
        self, candidate_text: str, *, max_suggestions: int = 5
    ) -> list[SearchSuggestion]:
        """Return up to ``max_suggestions`` queries, most relevant first.

        Returns an empty list (never raises) if the LLM output can't be parsed —
        callers fall back to a manual search.
        """
        try:
            raw = self._llm.ask(self._build_prompt(candidate_text, max_suggestions))
        except Exception as exc:  # noqa: BLE001 — degrade to manual search
            logger.warning("search-suggestion LLM call failed: %s", exc)
            return []

        cleaned = strip_json_fences(raw)
        try:
            data = extract_first_json(cleaned)
            if not isinstance(data, list):
                return []
            items = [SearchSuggestion.model_validate(d) for d in data]
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            logger.warning("search-suggestion parse failed: %s", exc)
            return []

        return [s for s in items if s.keyword.strip()][:max_suggestions]
