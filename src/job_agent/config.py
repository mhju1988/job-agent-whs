"""Application settings loaded from .env via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MissingCredentialsError(RuntimeError):
    """Raised when live credentials are required but not configured."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gwdg_api_base: str = Field(default="https://chat-ai.academiccloud.de/v1")
    gwdg_api_key: str = Field(default="")
    gwdg_model: str = Field(default="meta-llama-3.1-8b-instruct")
    gwdg_embed_model: str = Field(default="e5-mistral-7b-instruct")

    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")

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
