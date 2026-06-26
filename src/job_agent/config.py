"""Application settings loaded from .env via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the project root (this file lives at <root>/src/job_agent/config.py),
# so settings load correctly regardless of the caller's working directory
# (Streamlit, scripts run from subdirectories, IDEs, etc.).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class MissingCredentialsError(RuntimeError):
    """Raised when live credentials are required but not configured."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    gwdg_api_base: str = Field(default="https://chat-ai.academiccloud.de/v1")
    gwdg_api_key: str = Field(default="")
    gwdg_model: str = Field(default="apertus-70b-instruct-2509")
    gwdg_embed_model: str = Field(default="multilingual-e5-large-instruct")
    # Per-request timeout for GWDG LLM calls (seconds). Prevents hung requests
    # from blocking the Matcher/Writer forever when GWDG stops responding mid-run.
    gwdg_timeout: int = Field(default=120)

    # NVIDIA NIM — all optional; blank nim_api_key disables NIM entirely
    nim_api_base: str = Field(default="https://integrate.api.nvidia.com/v1")
    nim_api_key: str = Field(default="")
    nim_model: str = Field(default="meta/llama-3.1-70b-instruct")
    nim_timeout: int = Field(default=30)
    nim_health_interval_s: int = Field(default=60, ge=5)

    # Max concurrent LLM calls in the matcher scoring loop (env MATCHER_MAX_CONCURRENCY).
    # Conservative default to avoid GWDG 429s; tune per environment.
    matcher_max_concurrency: int = Field(default=4, ge=1)

    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")
    # Anon (publishable) key — used by the API's per-request client together with
    # the caller's JWT so Postgres RLS resolves auth.uid() to the user. The
    # service-role `supabase_key` above bypasses RLS and stays for scripts/tests.
    supabase_anon_key: str = Field(default="")
    # Project JWT secret — the API verifies Supabase access tokens (HS256) with it.
    supabase_jwt_secret: str = Field(default="")
    # Comma-separated allowed CORS origins for the API (Next.js dev server default).
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    # Optional secondary job source (RapidAPI / JSearch). When blank, the
    # source is disabled and ScoutAgent simply omits it from dispatch.
    rapidapi_key: str = Field(default="")

    log_level: str = Field(default="INFO")
    artifacts_dir: Path = Field(default=Path("./artifacts"))

    def require_live_credentials(self) -> None:
        """Fail fast if any live-call credentials are missing.

        Call this from code paths that hit GWDG or Supabase. Unit tests can
        still instantiate `Settings()` without keys.
        """
        missing = [
            name
            for name, val in (
                ("GWDG_API_KEY", self.gwdg_api_key),
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
            )
            if not val
        ]
        if missing:
            raise MissingCredentialsError(
                f"Missing required env vars: {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
