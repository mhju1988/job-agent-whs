"""Thin Supabase client wrapper with dependency-injection support."""

from __future__ import annotations

from supabase import Client, create_client

from job_agent.config import MissingCredentialsError, Settings, get_settings


class SupabaseClient:
    """Wraps the Supabase SDK client.

    Two construction paths:

    * Default / service-role — ``SupabaseClient()`` builds a client from
      ``supabase_key`` (service role; bypasses RLS). Used by scripts and tests.
    * Per-user / RLS-bound — ``SupabaseClient.for_user(jwt)`` builds a client
      from the anon key and authenticates PostgREST with the caller's JWT so
      Postgres ``auth.uid()`` resolves to that user and RLS is enforced.

    Dependency-injection: pass ``client`` to inject a fake in tests. When
    ``settings`` is omitted, ``get_settings()`` is used (the cached singleton),
    matching the pattern established in ``BaseAgent``.
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

    @classmethod
    def for_user(
        cls,
        access_token: str,
        *,
        settings: Settings | None = None,
    ) -> SupabaseClient:
        """Build an RLS-bound client for the user identified by ``access_token``.

        Uses the anon key (not the service-role key) so Postgres RLS is active,
        then authenticates PostgREST with the user's JWT so ``auth.uid()``
        resolves to that user inside every policy check.
        """
        _settings = settings if settings is not None else get_settings()
        if not _settings.supabase_url or not _settings.supabase_anon_key:
            raise MissingCredentialsError(
                "for_user() requires SUPABASE_URL and SUPABASE_ANON_KEY. "
                "Copy .env.example to .env and fill them in."
            )
        client = create_client(_settings.supabase_url, _settings.supabase_anon_key)
        client.postgrest.auth(access_token)
        return cls(client=client)

    @property
    def raw(self) -> Client:
        """Return the underlying Supabase ``Client`` for direct table access.

        TODO Sprint 2: add table-scoped accessor methods (e.g. ``jobs_table``,
        ``applications_table``) so callers do not build ad-hoc queries against
        the raw client across the codebase.
        """
        return self._client
