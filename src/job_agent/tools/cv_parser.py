"""CV PDF parser: extracts structured Profile data from a PDF resume."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pypdf
from pydantic import ValidationError

from job_agent.agents.base_agent import JSON_ONLY_PREAMBLE, BaseAgent
from job_agent.models.profile import Profile
from job_agent.tools.llm_json import strip_json_fences


class CVParseError(Exception):
    """Raised when the CV cannot be parsed into a valid Profile."""


_SCHEMA_HINT = """
Return ONLY a JSON object with this exact structure (no extra keys):
{
  "full_name": "<string or null — candidate full name (first + last) as on the CV; null if absent>",
  "summary": "<string or null>",
  "skills": ["<string>", ...],
  "experience": [
    {
      "title": "<string>",
      "company": "<string>",
      "start": "<string or null>",
      "end": "<string or null>",
      "description": "<string or null>"
    }
  ],
  "education": [
    {
      "degree": "<string>",
      "institution": "<string>",
      "field": "<string or null>",
      "start": "<string or null>",
      "end": "<string or null>"
    }
  ],
  "languages": ["<string>", ...]
}
""".strip()


def _sanitise_list_of_dicts(
    data: dict[str, Any], key: str, required_string_fields: tuple[str, ...]
) -> None:
    """Drop entries from ``data[key]`` whose required string fields are null/empty.

    Mutates ``data`` in place. No-op if ``data[key]`` is missing or not a list.
    This protects against flaky LLM output where a JSON object lists an
    incomplete entry (e.g. an education row with ``"degree": null``).
    """
    items = data.get(key)
    if not isinstance(items, list):
        return
    data[key] = [
        item
        for item in items
        if isinstance(item, dict)
        and all(isinstance(item.get(f), str) and item[f].strip() for f in required_string_fields)
    ]


class CVParser:
    """Two-stage CV extractor: PDF text → LLM → Profile."""

    def __init__(
        self,
        llm_agent: BaseAgent | None = None,
        pdf_reader_factory: Callable[[str | Path], Any] | None = None,
    ) -> None:
        self._llm_agent = llm_agent if llm_agent is not None else BaseAgent()
        self._pdf_reader_factory = (
            pdf_reader_factory if pdf_reader_factory is not None else pypdf.PdfReader
        )

    def parse(self, pdf_path: str | Path) -> Profile:
        """Extract a Profile from a PDF CV file."""
        reader = self._pdf_reader_factory(pdf_path)
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()

        if not text:
            raise CVParseError("no text extracted")

        prompt = (
            f"{JSON_ONLY_PREAMBLE}"
            f"Extract the CV information from the text below using this schema.\n\n"
            f"Schema:\n{_SCHEMA_HINT}\n\n"
            f"CV text:\n{text}"
        )

        raw = self._llm_agent.ask(prompt)
        raw = strip_json_fences(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CVParseError(f"LLM returned invalid JSON: {exc}") from exc

        # Defensive sanitisation — the LLM occasionally returns null/empty
        # values for required string fields (e.g. "degree": null when an
        # entry on the CV is a non-degree course). Drop such entries rather
        # than letting Profile.model_validate raise.
        _sanitise_list_of_dicts(data, "education", ("degree", "institution"))
        _sanitise_list_of_dicts(data, "experience", ("title", "company"))

        try:
            return Profile.model_validate(data)
        except ValidationError as exc:
            raise CVParseError(f"JSON does not match Profile schema: {exc}") from exc

    def parse_bytes(self, raw: bytes) -> Profile:
        """Extract a Profile from raw PDF bytes (e.g. from a Streamlit upload).

        Writes the bytes to a temporary file and delegates to :meth:`parse`,
        so the existing path-based implementation stays the single source of
        truth.
        """
        if not raw:
            raise CVParseError("empty upload (0 bytes)")

        # On Windows, the temp file handle must be closed before pypdf can
        # reopen the path — `delete=False` + leaving the `with` block first
        # avoids `PermissionError` on the second open.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(raw)
            tmp_path_str = tmp.name
        try:
            return self.parse(tmp_path_str)
        finally:
            Path(tmp_path_str).unlink(missing_ok=True)
