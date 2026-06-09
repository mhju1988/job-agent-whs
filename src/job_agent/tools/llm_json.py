"""Utility for stripping markdown code fences from LLM JSON responses."""

from __future__ import annotations

import re

# `(?:json)?` makes the language tag optional, so a single regex handles both
# ```json ... ``` and bare ``` ... ``` fences.
_FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def strip_json_fences(raw: str) -> str:
    """Remove an optional markdown code fence from *raw*.

    Handles ```json ... ```, plain ``` ... ```, and ungated text alike.
    Returns the content stripped of leading/trailing whitespace.
    """
    text = raw.strip()
    m = _FENCE.match(text)
    if m:
        return m.group(1).strip()
    return text
