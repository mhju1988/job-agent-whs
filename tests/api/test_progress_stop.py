"""run_agent_sse plumbs a should_stop callable into work() and sets it on close."""

from __future__ import annotations

from typing import Any

import pytest

from job_agent.api.progress import run_agent_sse


@pytest.mark.asyncio
async def test_work_receives_should_stop_callable_false_while_running() -> None:
    captured: dict[str, Any] = {}

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        captured["callable"] = callable(should_stop)
        captured["initial"] = should_stop()  # not closed yet -> False
        on_progress({"stage": "x"})
        return {"done": True}

    gen = run_agent_sse(work).body_iterator
    events = [ev async for ev in gen]

    assert captured["callable"] is True
    assert captured["initial"] is False
    assert any(e["event"] == "progress" for e in events)
    assert any(e["event"] == "result" for e in events)


@pytest.mark.asyncio
async def test_should_stop_becomes_true_after_generator_close() -> None:
    captured: dict[str, Any] = {}

    def work(on_progress: Any, should_stop: Any) -> dict[str, Any]:
        captured["should_stop"] = should_stop
        on_progress({"stage": "x"})
        return {"done": True}

    gen = run_agent_sse(work).body_iterator
    first = await gen.__anext__()
    assert first["event"] == "progress"
    assert captured["should_stop"]() is False  # alive
    await gen.aclose()                          # simulate client disconnect
    assert captured["should_stop"]() is True    # finally set the event
