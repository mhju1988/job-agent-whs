"""Cover letter renderer: LLM content generation + Jinja2 template rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

import jinja2
from jinja2 import PackageLoader, StrictUndefined
from pydantic import ValidationError

from job_agent.agents.base_agent import JSON_ONLY_PREAMBLE, BaseAgent
from job_agent.models.cover_letter import CoverLetterContent
from job_agent.models.job import Job
from job_agent.models.profile import Profile
from job_agent.tools.llm_json import strip_json_fences

Language = Literal["en", "de"]

_TEMPLATE_BY_LANG: dict[Language, str] = {
    "en": "cover_letter.jinja2",
    "de": "cover_letter_de.jinja2",
}


class CoverLetterError(Exception):
    """Raised when cover letter generation or rendering fails."""


@dataclass(frozen=True)
class CandidateContext:
    """Minimal typed shim passed into the Jinja template as `candidate`."""

    name: str


_SCHEMA_HINT = """
Return ONLY a JSON object with this exact structure (no extra keys):
{
  "opening": "<string: 1-2 sentences greeting and hook>",
  "body": "<string: 1-2 short paragraphs of substance>",
  "closing": "<string: 1 sentence sign-off>"
}
""".strip()


class CoverLetterRenderer:
    """Two-stage cover letter generator: LLM content → Jinja2 template render."""

    def __init__(
        self,
        llm_agent: BaseAgent | None = None,
        env: jinja2.Environment | None = None,
        language: Language = "en",
    ) -> None:
        self._llm_agent = llm_agent if llm_agent is not None else BaseAgent()
        self._env = (
            env
            if env is not None
            else jinja2.Environment(
                loader=PackageLoader("job_agent", "templates"),
                autoescape=False,
                undefined=StrictUndefined,
            )
        )
        if language not in _TEMPLATE_BY_LANG:
            raise CoverLetterError(f"unsupported language: {language!r}")
        self._language: Language = language
        self._template_name: str = _TEMPLATE_BY_LANG[language]

    def render(
        self,
        *,
        candidate_name: str,
        profile: Profile,
        job: Job,
        matched_skills: list[str],
        gaps_addressed: list[str] | None = None,
    ) -> str:
        """Generate and render a cover letter for the given job and candidate."""
        gaps = gaps_addressed or []

        # Build prompt for LLM
        skills_text = ", ".join(matched_skills)
        gaps_text = ", ".join(gaps) if gaps else "none"
        profile_summary = profile.summary or "No summary provided."
        profile_skills = ", ".join(profile.skills) if profile.skills else "none listed"

        lang_hint = (
            "Write the cover letter in German.\n"
            if self._language == "de"
            else ""
        )
        prompt = (
            f"{JSON_ONLY_PREAMBLE}"
            f"Write cover letter content for a job application using this schema.\n"
            f"{lang_hint}\n"
            f"Schema:\n{_SCHEMA_HINT}\n\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company or 'the company'}\n"
            f"Job description: {job.description or 'not provided'}\n"
            f"Candidate name: {candidate_name}\n"
            f"Candidate summary: {profile_summary}\n"
            f"Candidate skills: {profile_skills}\n"
            f"Matched skills for this role: {skills_text}\n"
            f"Skill gaps candidate is developing: {gaps_text}\n"
        )

        raw = self._llm_agent.ask(prompt)
        raw = strip_json_fences(raw)

        try:
            # strict=False tolerates literal control characters (raw newlines,
            # tabs) inside string values — LLMs, especially on multi-paragraph
            # German prose, routinely emit these instead of escaped "\n".
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError as exc:
            raise CoverLetterError(f"LLM returned invalid JSON: {exc}") from exc

        try:
            content = CoverLetterContent.model_validate(data)
        except ValidationError as exc:
            raise CoverLetterError(
                f"JSON does not match CoverLetterContent schema: {exc}"
            ) from exc

        # Build template context
        candidate_obj = CandidateContext(name=candidate_name)
        matched_skills_str = skills_text
        gaps_addressed_str = ", ".join(gaps) if gaps else ""

        try:
            template = self._env.get_template(self._template_name)
            rendered = template.render(
                candidate=candidate_obj,
                # Profile is also threaded into the template so the signature
                # line can use the real CV name (``profile.full_name``) when
                # available, falling back to "Your Name" inside the template.
                profile=profile,
                job=job,
                content=content,
                matched_skills=matched_skills_str,
                gaps_addressed=gaps_addressed_str,
            )
        except jinja2.UndefinedError as exc:
            raise CoverLetterError(f"Unresolved template placeholder: {exc}") from exc

        # Defence in depth: ensure no unresolved placeholders remain
        if "{{" in rendered:
            raise CoverLetterError(
                "unresolved placeholders detected in render output"
            )

        return rendered
