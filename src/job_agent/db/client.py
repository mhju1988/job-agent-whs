"""Thin Supabase client wrapper with dependency-injection support."""

from supabase import Client, create_client

from job_agent.config import Settings, get_settings


class SupabaseClient:
    """Wraps the Supabase SDK client.

    Dependency-injection pattern: pass ``client`` in tests to avoid live calls.
    When ``client`` is omitted the wrapper calls
    ``settings.require_live_credentials()`` before building the real client,
    so misconfigured environments fail fast.

    When ``settings`` is omitted, ``get_settings()`` is used (the cached
    singleton), matching the pattern established in ``BaseAgent``.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: Client | None = None,
    ) -> None:
        if client is not None:
            self._client: Client = client
            return
        _settings = settings if settings is not None else get_settings()
        _settings.require_live_credentials()
        self._client = create_client(_settings.supabase_url, _settings.supabase_key)

    @property
    def raw(self) -> Client:
        """Return the underlying Supabase ``Client`` for direct table access.

        TODO Sprint 2: add table-scoped accessor methods (e.g. ``jobs_table``,
        ``applications_table``) so callers do not build ad-hoc queries against
        the raw client across the codebase.
        """
        return self._client
