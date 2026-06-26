"""Framework-free match filtering for the API layer.

Sorting now lives in the frontend (lib/match-sort.ts) as the single source of
truth; this module only applies the score-threshold filter.
"""

from __future__ import annotations

from typing import Any


def filter_matches(
    matches: list[dict[str, Any]], threshold: int
) -> list[dict[str, Any]]:
    """Drop unscored rows and rows below ``threshold``.

    Rows with ``score is None`` (should not occur — the column is NOT NULL —
    but defensive) are excluded. Ordering is the caller's responsibility (the
    SQL query returns score-desc); the frontend re-sorts for display.
    """
    return [
        m for m in matches if m.get("score") is not None and m["score"] >= threshold
    ]
