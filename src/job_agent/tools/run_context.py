"""Lightweight run context carried via contextvars for the observability layer."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
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
