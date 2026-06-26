"""Lightweight run context carried via contextvars for the observability layer."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Optional progress sink (same DI shape as the obs= sink). Each call receives a
# small JSON-able dict; the API streams these as SSE events.
ProgressCb = Callable[[dict[str, Any]], None]

# Optional stop signal (loop->worker bridge, mirroring ProgressCb's worker->loop
# bridge). Returns True when the run should stop at its next loop boundary.
StopCb = Callable[[], bool]


def emit_progress(cb: ProgressCb | None, **fields: Any) -> None:
    """Call the progress callback with ``fields`` as a dict, if a sink is set."""
    if cb is not None:
        cb(fields)


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    started_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


_current_run: ContextVar[RunContext | None] = ContextVar(
    "current_run", default=None
)


def start_run(agent_name: str) -> RunContext:
    """Create a new RunContext and set it as the active run for this thread."""
    ctx = RunContext(agent_name=agent_name)
    _current_run.set(ctx)
    return ctx


def get_current_run() -> RunContext | None:
    """Return the active RunContext for this thread, or None if not in a run."""
    return _current_run.get()
