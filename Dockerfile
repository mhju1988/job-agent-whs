FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy project metadata and lockfile
COPY uv.lock pyproject.toml README.md ./

# Copy source code
COPY src/ ./src/

# Install dependencies and the job_agent package
RUN uv sync --frozen --no-dev

# Start command (shell form so $PORT expands at runtime; fallback 8000 for local docker run).
# --no-sync: the image is already synced at build time (line above) with --no-dev.
# Without it, `uv run` re-resolves on every start and tries to fetch dev-only deps,
# which fails in a network-restricted container and slows down cold starts.
CMD uv run --no-sync uvicorn job_agent.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
