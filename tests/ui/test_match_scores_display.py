"""Tests for the Matches tab match-card rendering (post-migration 008)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_agent.ui.app import _render_match_card, _tag_chips


def _full_row() -> dict:
    return {
        "id": "ms-uuid-1",
        "job_id": "job-uuid-1",
        "score": 87,
        "matched_skills": ["Python", "SQL"],
        "gaps": ["AWS"],
        "rationale": "Strong backend overlap; cloud experience is the gap.",
        "jobs": {"title": "Senior Python Dev", "company": "Acme GmbH"},
    }


def _null_analysis_row() -> dict:
    """Legacy row from before migration 008 / before LLM gap analysis."""
    return {
        "id": "ms-uuid-2",
        "job_id": "job-uuid-2",
        "score": 70,
        "matched_skills": None,
        "gaps": None,
        "rationale": None,
        "jobs": {"title": "Backend Engineer", "company": "BetaCorp"},
    }


# ---------------------------------------------------------------------------


def test_renders_matched_skills_and_gaps() -> None:
    """All three fields populated → markdown chips + caption + score rendered."""
    with patch("job_agent.ui.app.st") as st_mock:
        # st.container, st.columns return context managers — make them work.
        st_mock.container.return_value.__enter__ = lambda self: self
        st_mock.container.return_value.__exit__ = lambda self, *a: None
        col1, col2 = MagicMock(), MagicMock()
        for col in (col1, col2):
            col.__enter__ = lambda self: self
            col.__exit__ = lambda self, *a: None
        st_mock.columns.return_value = (col1, col2)
        st_mock.button.return_value = False

        _render_match_card(_full_row())

    # Collect every text passed to st.markdown across the run.
    markdown_calls = [c.args[0] for c in st_mock.markdown.call_args_list]
    joined = " ".join(markdown_calls)
    assert "Python" in joined
    assert "SQL" in joined
    assert "AWS" in joined
    assert "Matched skills" in joined
    assert "Gaps" in joined

    # Rationale rendered as a caption.
    caption_calls = [c.args[0] for c in st_mock.caption.call_args_list]
    assert any("Strong backend overlap" in c for c in caption_calls)

    # Score metric pushed.
    st_mock.metric.assert_called_once()
    assert st_mock.metric.call_args.args == ("Score", 87)


def test_tag_chips_escapes_html_to_block_xss() -> None:
    """LLM-emitted strings with HTML must be escaped, not rendered as markup."""
    out = _tag_chips(["<b>bad</b>", "</span><script>alert(1)</script>"], "16a34a")
    # Escaped form is present.
    assert "&lt;b&gt;bad&lt;/b&gt;" in out
    assert "&lt;script&gt;" in out
    # Raw injection vectors are NOT present as live tags.
    assert "<b>bad</b>" not in out
    assert "<script>" not in out
    # The wrapper span is still well-formed — exactly two opening + closing
    # span tags from our template, no extras from the injection.
    assert out.count("<span") == 2
    assert out.count("</span>") == 2


def test_handles_null_analysis_gracefully() -> None:
    """Legacy row with all-None analysis → fallback caption, no crash."""
    with patch("job_agent.ui.app.st") as st_mock:
        st_mock.container.return_value.__enter__ = lambda self: self
        st_mock.container.return_value.__exit__ = lambda self, *a: None
        col1, col2 = MagicMock(), MagicMock()
        for col in (col1, col2):
            col.__enter__ = lambda self: self
            col.__exit__ = lambda self, *a: None
        st_mock.columns.return_value = (col1, col2)
        st_mock.button.return_value = False

        _render_match_card(_null_analysis_row())

    caption_calls = [c.args[0] for c in st_mock.caption.call_args_list]
    assert any("No analysis available" in c for c in caption_calls)
    # No chip markdown should have been emitted.
    markdown_calls = [c.args[0] for c in st_mock.markdown.call_args_list]
    assert not any("Matched skills" in c for c in markdown_calls)
    assert not any("Gaps" in c for c in markdown_calls)
