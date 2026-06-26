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
from job_agent.models.profile import Experience, Profile
from job_agent.tools.cover_letter_validator import LetterIssue, validate_letter
from job_agent.tools.llm_json import extract_first_json, strip_json_fences

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

#: Negative constraints appended to every content prompt. Small models default
#: to generic, apologetic, or fabricated prose; spelling out the "do NOT" rules
#: moves them substantially. See improvement A4.
_NEGATIVE_INSTRUCTIONS = """
Hard rules — things you must NOT do:
- Do NOT invent experience, employers, metrics, or qualifications not in the candidate data.
- Do NOT use stock openers like "I am writing to apply for" or "To whom it may concern".
- Do NOT use filler or hollow superlatives ("perfect fit", "I am confident that", "fast-paced").
- Do NOT apologise for skill gaps; if a gap is mentioned, frame it as active learning.
- Ground at least one claim in the body in a SPECIFIC past role from the candidate data.
""".strip()

#: How many times the generate→validate loop will retry after a failing draft.
#: Total attempts are MAX_RETRIES + 1 (the initial draft plus retries).
MAX_RETRIES = 2


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

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @staticmethod
    def _format_experience(experience: list[Experience], limit: int = 4) -> str:
        """Render up to *limit* roles as compact lines for the LLM prompt.

        Without this, the LLM never sees the candidate's actual work history
        and can only produce a generic letter (improvement A1). Cap the count
        so a long history does not blow up the prompt.
        """
        if not experience:
            return "none listed"
        lines: list[str] = []
        for exp in experience[:limit]:
            date_range = f"{exp.start or '?'} – {exp.end or 'present'}"
            line = f"- {exp.title} at {exp.company} ({date_range})"
            if exp.description:
                line += f": {exp.description}"
            lines.append(line)
        return "\n".join(lines)

    def _build_prompt(
        self,
        *,
        profile: Profile,
        job: Job,
        candidate_name: str,
        matched_skills: list[str],
        gaps: list[str],
    ) -> str:
        """Assemble the content-generation prompt.

        Improvement A1: candidate work history is included so the model can
        ground the body in a concrete past role. A4: explicit negative
        instructions suppress filler/fabrication.
        """
        skills_text = ", ".join(matched_skills)
        gaps_text = ", ".join(gaps) if gaps else "none"
        profile_summary = profile.summary or "No summary provided."
        profile_skills = ", ".join(profile.skills) if profile.skills else "none listed"
        experience_text = self._format_experience(profile.experience)

        lang_hint = (
            "Write the cover letter in German.\n"
            if self._language == "de"
            else ""
        )
        return (
            f"{JSON_ONLY_PREAMBLE}"
            f"Write cover letter content for a job application using this schema.\n"
            f"{lang_hint}\n"
            f"Schema:\n{_SCHEMA_HINT}\n\n"
            f"{_NEGATIVE_INSTRUCTIONS}\n\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company or 'the company'}\n"
            f"Job description: {job.description or 'not provided'}\n"
            f"Candidate name: {candidate_name}\n"
            f"Candidate summary: {profile_summary}\n"
            f"Candidate skills: {profile_skills}\n"
            f"Candidate experience:\n{experience_text}\n"
            f"Matched skills for this role: {skills_text}\n"
            f"Skill gaps candidate is developing: {gaps_text}\n"
        )

    # ------------------------------------------------------------------
    # LLM call + validation loop
    # ------------------------------------------------------------------

    def _generate_content(
        self,
        *,
        prompt: str,
        previous_issues: list[LetterIssue] | None = None,
    ) -> CoverLetterContent:
        """Call the LLM, parse JSON, validate — one attempt.

        On a quality failure the caller (``render``) inspects the raised
        ``CoverLetterError``'s ``issues`` attribute to build a repair prompt.
        """
        full_prompt = prompt
        if previous_issues:
            # Feed the validator's findings back so the model can repair the
            # specific defects rather than blindy regenerating.
            findings = "\n".join(f"- {iss}" for iss in previous_issues)
            full_prompt = (
                f"{prompt}\n\n"
                "Your previous attempt had these problems:\n"
                f"{findings}\n\n"
                "Fix every problem above and return the corrected JSON object only."
            )

        raw = self._llm_agent.ask(full_prompt)
        raw = strip_json_fences(raw)

        try:
            data = extract_first_json(raw)
        except json.JSONDecodeError as exc:
            raise CoverLetterError(f"LLM returned invalid JSON: {exc}") from exc

        try:
            content = CoverLetterContent.model_validate(data)
        except ValidationError as exc:
            raise CoverLetterError(
                f"JSON does not match CoverLetterContent schema: {exc}"
            ) from exc

        issues = validate_letter(content, language=self._language)
        if issues:
            # Attach for the retry loop; not raised yet so callers that only do
            # one attempt (e.g. tests) can still surface the parsed content.
            err = CoverLetterError(
                "cover letter failed content validation: "
                + "; ".join(str(i) for i in issues)
            )
            # Stash findings on the exception so the retry loop can feed them
            # back to the model for a targeted repair.
            err.issues = issues  # type: ignore[attr-defined]
            raise err

        return content

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        *,
        candidate_name: str,
        profile: Profile,
        job: Job,
        matched_skills: list[str],
        gaps_addressed: list[str] | None = None,
    ) -> str:
        """Generate and render a cover letter for the given job and candidate.

        Runs a bounded generate→validate→repair loop (improvement B1): the
        initial draft is validated for quality (A3); on failure, the model is
        re-prompted with the specific defects up to ``MAX_RETRIES`` times.
        """
        gaps = gaps_addressed or []
        base_prompt = self._build_prompt(
            profile=profile,
            job=job,
            candidate_name=candidate_name,
            matched_skills=matched_skills,
            gaps=gaps,
        )

        content: CoverLetterContent
        last_error: CoverLetterError | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                content = self._generate_content(
                    prompt=base_prompt,
                    previous_issues=(
                        last_error.issues
                        if last_error is not None and hasattr(last_error, "issues")
                        else None
                    ),
                )
                break
            except CoverLetterError as exc:
                # Validation failures carry repairable issues → retry; anything
                # else (JSON/schema/unresolved-placeholder) is not repairable.
                if hasattr(exc, "issues") and attempt < MAX_RETRIES:
                    last_error = exc
                    continue
                raise
        else:  # pragma: no cover — loop only exits via break or raise above
            raise CoverLetterError("exhausted retries without producing content")

        # Build template context
        candidate_obj = CandidateContext(name=candidate_name)
        matched_skills_str = ", ".join(matched_skills)
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
