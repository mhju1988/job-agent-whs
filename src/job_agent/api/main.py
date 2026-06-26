"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_agent.api.routers import (
    applications,
    data,
    jobs,
    matches,
    meta,
    observability,
    profile,
    runs,
    search,
)
from job_agent.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Job Agent API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (
        meta,
        profile,
        jobs,
        matches,
        applications,
        runs,
        data,
        observability,
        search,
    ):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
