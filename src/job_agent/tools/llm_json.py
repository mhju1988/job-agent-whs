"""Utility for stripping markdown code fences from LLM JSON responses."""

from __future__ import annotations

import json
import re
from typing import Any

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


def extract_first_json(text: str) -> Any:
    """Parse the first JSON value in *text*, tolerating surrounding prose.

    Some chat models (e.g. apertus-70b) append commentary after the closing
    ``]`` or ``}`` — plain ``json.loads`` then raises "Extra data".
    ``raw_decode`` parses just the first complete JSON value and ignores
    everything after it. ``strict=False`` tolerates literal control characters
    inside strings.

    The search starts at the earliest ``{`` or ``[`` in the text so that
    leading prose is skipped but nested values inside the top-level structure
    are not mistaken for the root value.

    Raises ``json.JSONDecodeError`` if no JSON value is found.
    """
    decoder = json.JSONDecoder(strict=False)
    obj_pos = text.find("{")
    arr_pos = text.find("[")
    # Pick whichever opener appears first; -1 means absent so treat as ∞.
    if obj_pos == -1 and arr_pos == -1:
        raise json.JSONDecodeError("no JSON object or array found", text, 0)
    if obj_pos == -1:
        start = arr_pos
    elif arr_pos == -1:
        start = obj_pos
    else:
        start = min(obj_pos, arr_pos)
    obj, _ = decoder.raw_decode(text[start:])
    return obj
