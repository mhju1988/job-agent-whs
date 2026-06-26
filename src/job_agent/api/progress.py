"""SSE helper: run a sync agent in a thread, stream ProgressEvents + a result."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

from sse_starlette.sse import EventSourceResponse

from job_agent.tools.run_context import ProgressCb, StopCb

_log = logging.getLogger(__name__)


def run_agent_sse(
    work: Callable[[ProgressCb, StopCb], dict[str, Any]],
) -> EventSourceResponse:
    """Stream an agent run as Server-Sent Events.

    ``work(on_progress, should_stop)`` runs the (synchronous) agent and returns
    a JSON-able result dict. ``should_stop()`` returns True once the client
    disconnects (the generator's ``finally`` sets a ``threading.Event``); the
    agent reads it to break at a loop boundary. Progress dicts pushed via
    ``on_progress`` are streamed as ``progress`` events; the return value as a
    terminal ``result`` event; any exception as a terminal ``error`` event. The
    agent runs in a worker thread so the event loop stays free to drain the queue.

    The loop + queue are created inside the generator so this works whether the
    route handler is sync (run in a worker thread) or async.
    """

    async def _events() -> AsyncIterator[dict[str, str]]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        stop_event = threading.Event()

        def on_progress(event: dict[str, Any]) -> None:
            # Called from the worker thread — hop back onto the loop thread-safely.
            loop.call_soon_threadsafe(queue.put_nowait, {"_type": "progress", **event})

        async def _runner() -> None:
            try:
                result = await asyncio.to_thread(work, on_progress, stop_event.is_set)
                await queue.put({"_type": "result", **result})
            except Exception as exc:  # noqa: BLE001 — surfaced as an error event
                # Preserve the full traceback server-side before shipping the
                # (string-only) error to the browser. The RunContextFilter will
                # also stamp the active run_id/agent_name onto this record.
                _log.exception("agent run failed")
                await queue.put({"_type": "error", "message": str(exc)})

        task = asyncio.create_task(_runner())
        try:
            while True:
                item = await queue.get()
                etype = item.pop("_type")
                yield {"event": etype, "data": json.dumps(item)}
                if etype in ("result", "error"):
                    break
        finally:
            # Client disconnect (or normal completion): tell the worker thread to
            # stop at its next loop boundary. The thread can't be force-killed (a
            # Python limitation), but a cooperative should_stop() lets it break
            # early and run its partial-result upsert instead of the full batch.
            # Then cancel the runner so we don't await a task forever; the event
            # loop is freed even though the worker thread runs on to its boundary.
            stop_event.set()
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return EventSourceResponse(_events())
