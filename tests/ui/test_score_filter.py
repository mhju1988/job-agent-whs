"""Tests for the Matches-tab score threshold filter + sort selector."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from job_agent.ui.app import (
    SORT_HIGH_LOW,
    SORT_LOW_HIGH,
    SORT_RECENT,
    _filter_and_sort_matches,
    _render_matches_tab,
)


def _row(
    score: int,
    *,
    created_at: str = "2026-01-01T00:00:00Z",
    ms_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": ms_id or f"ms-{score}",
        "job_id": f"job-{score}",
        "score": score,
        "matched_skills": [],
        "gaps": [],
        "rationale": "ok",
        "created_at": created_at,
        "jobs": {"title": f"Job {score}", "company": "Acme"},
    }


# ---------------------------------------------------------------------------
# _filter_and_sort_matches — pure-helper unit tests
# ---------------------------------------------------------------------------


def test_threshold_filter_hides_low_scores() -> None:
    matches = [_row(90), _row(60), _row(30)]
    visible = _filter_and_sort_matches(matches, threshold=50, sort_mode=SORT_HIGH_LOW)
    assert [r["score"] for r in visible] == [90, 60]


def test_threshold_zero_shows_all() -> None:
    matches = [_row(90), _row(60), _row(30)]
    visible = _filter_and_sort_matches(matches, threshold=0, sort_mode=SORT_HIGH_LOW)
    assert len(visible) == 3


def test_threshold_100_shows_only_perfect() -> None:
    matches = [_row(100), _row(99), _row(50)]
    visible = _filter_and_sort_matches(matches, threshold=100, sort_mode=SORT_HIGH_LOW)
    assert [r["score"] for r in visible] == [100]


def test_sort_high_to_low() -> None:
    matches = [_row(30), _row(90), _row(60)]
    visible = _filter_and_sort_matches(matches, threshold=0, sort_mode=SORT_HIGH_LOW)
    assert [r["score"] for r in visible] == [90, 60, 30]


def test_sort_low_to_high() -> None:
    matches = [_row(90), _row(30), _row(60)]
    visible = _filter_and_sort_matches(matches, threshold=0, sort_mode=SORT_LOW_HIGH)
    assert [r["score"] for r in visible] == [30, 60, 90]


def test_sort_most_recent() -> None:
    matches = [
        _row(50, created_at="2026-01-01T00:00:00Z", ms_id="old"),
        _row(50, created_at="2026-05-20T00:00:00Z", ms_id="new"),
        _row(50, created_at="2026-03-15T00:00:00Z", ms_id="mid"),
    ]
    visible = _filter_and_sort_matches(matches, threshold=0, sort_mode=SORT_RECENT)
    assert [r["id"] for r in visible] == ["new", "mid", "old"]


def test_unknown_sort_mode_falls_through_to_default() -> None:
    matches = [_row(30), _row(90), _row(60)]
    visible = _filter_and_sort_matches(matches, threshold=0, sort_mode="bogus")
    # Defaults to high → low.
    assert [r["score"] for r in visible] == [90, 60, 30]


def test_filter_handles_none_score_gracefully() -> None:
    """A row with score=None is treated as 0 (and filtered out at threshold > 0)."""
    matches = [_row(80), {"id": "x", "job_id": "y", "score": None, "jobs": {}}]
    visible = _filter_and_sort_matches(matches, threshold=50, sort_mode=SORT_HIGH_LOW)
    assert [r["score"] for r in visible] == [80]


# ---------------------------------------------------------------------------
# _render_matches_tab — caption + rendered-card count
# ---------------------------------------------------------------------------


def _patch_tab_streamlit(threshold: int, sort_mode: str) -> Any:
    """Build a patched st mock whose slider/selectbox return the desired values."""
    st_mock = MagicMock()
    st_mock.slider.return_value = threshold
    st_mock.selectbox.return_value = sort_mode
    return st_mock


def test_caption_shows_correct_counts() -> None:
    rows = [_row(90), _row(60), _row(30)]
    db = MagicMock()
    db.raw.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = rows  # noqa: E501

    st_mock = _patch_tab_streamlit(threshold=50, sort_mode=SORT_HIGH_LOW)
    with (
        patch("job_agent.ui.app.st", st_mock),
        patch("job_agent.ui.app.get_db", return_value=db),
        patch("job_agent.ui.app._render_match_card") as render_card,
    ):
        _render_matches_tab()

    captions = [c.args[0] for c in st_mock.caption.call_args_list]
    assert any("Showing 2 of 3" in c and "score ≥ 50" in c for c in captions)
    # Only the two filtered rows were rendered.
    assert render_card.call_count == 2


def test_render_uses_sorted_filtered_order() -> None:
    rows = [_row(30), _row(90), _row(60)]
    db = MagicMock()
    db.raw.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = rows  # noqa: E501

    st_mock = _patch_tab_streamlit(threshold=0, sort_mode=SORT_HIGH_LOW)
    with (
        patch("job_agent.ui.app.st", st_mock),
        patch("job_agent.ui.app.get_db", return_value=db),
        patch("job_agent.ui.app._render_match_card") as render_card,
    ):
        _render_matches_tab()

    rendered_scores = [c.args[0]["score"] for c in render_card.call_args_list]
    assert rendered_scores == [90, 60, 30]
