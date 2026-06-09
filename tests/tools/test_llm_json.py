"""Tests for the strip_json_fences helper in tools/llm_json.py."""

from __future__ import annotations

from job_agent.tools.llm_json import strip_json_fences


def test_strip_plain_json() -> None:
    """No fence present — string returned stripped of whitespace only."""
    raw = '{"score": 80, "rationale": "ok"}'
    assert strip_json_fences(raw) == raw


def test_strip_json_fence_with_language() -> None:
    """```json ... ``` fence is stripped, inner JSON returned."""
    inner = '{"score": 80}'
    raw = f"```json\n{inner}\n```"
    assert strip_json_fences(raw) == inner


def test_strip_plain_fence() -> None:
    """``` ... ``` fence with no language tag is stripped."""
    inner = '{"gaps": ["Docker"]}'
    raw = f"```\n{inner}\n```"
    assert strip_json_fences(raw) == inner


def test_strip_preserves_leading_trailing_whitespace_inside_fence() -> None:
    """Inner content is stripped of surrounding whitespace."""
    inner = '{"score": 50}'
    raw = f"```json\n  {inner}  \n```"
    assert strip_json_fences(raw) == inner


def test_strip_no_modification_for_plain_text() -> None:
    """Plain text with no fences returns the stripped input unchanged."""
    raw = "  some text  "
    assert strip_json_fences(raw) == "some text"
