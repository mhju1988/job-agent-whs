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

# Start command (shell form so $PORT expands at runtime; fallback 8000 for local docker run)
CMD uv run uvicorn job_agent.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
