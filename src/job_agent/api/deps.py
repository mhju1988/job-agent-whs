"""FastAPI dependencies: Supabase-JWT auth + per-request RLS-bound DB."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from job_agent.config import Settings, get_settings
from job_agent.db.client import SupabaseClient

# Supabase issues either HS256 (legacy shared-secret) or asymmetric (ES256/RS256/
# EdDSA, the newer JWT-signing-keys feature) access tokens. We route by the
# token header's `alg`: HS256 verifies against the project secret; asymmetric
# verifies against the project JWKS.
_ASYMMETRIC_ALGS = ["ES256", "RS256", "EdDSA"]


@dataclass
class CurrentUser:
    """The authenticated caller: their Supabase user id, raw access token, and role."""

    user_id: str
    token: str
    role: str = "user"


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    """Cached JWKS client (caches fetched signing keys internally too)."""
    return PyJWKClient(jwks_url)


def _decode_claims(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a Supabase access token and return its full claim set.

    Tokens carry ``aud="authenticated"``. HS256 tokens are verified against
    ``supabase_jwt_secret``; asymmetric tokens against the project JWKS at
    ``{supabase_url}/auth/v1/.well-known/jwks.json``.
    """
    try:
        alg = str(jwt.get_unverified_header(token).get("alg", ""))
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Malformed token header") from exc

    try:
        if alg.startswith("HS"):
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status_code=500, detail="SUPABASE_JWT_SECRET not configured"
                )
            claims: dict[str, Any] = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            if not settings.supabase_url:
                raise HTTPException(status_code=500, detail="SUPABASE_URL not configured")
            jwks_url = (
                f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            )
            signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ASYMMETRIC_ALGS,
                audience="authenticated",
            )
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    return claims


def _decode_token(token: str, settings: Settings) -> str:
    """Verify a Supabase access token and return its ``sub`` (user id)."""
    claims = _decode_claims(token, settings)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return str(sub)


def _role_from_claims(claims: dict[str, Any]) -> str:
    app_metadata = claims.get("app_metadata")
    if isinstance(app_metadata, dict) and app_metadata.get("role") == "admin":
        return "admin"
    return "user"


def get_current_user(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract + verify the bearer token, yielding the authenticated user."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[7:].strip()
    claims = _decode_claims(token, settings)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return CurrentUser(user_id=str(sub), token=token, role=_role_from_claims(claims))


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Gate access to admin-only endpoints. Raises 403 for non-admin callers."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_user_db(user: CurrentUser = Depends(get_current_user)) -> SupabaseClient:
    """Per-request RLS-bound Supabase client for the authenticated user."""
    return SupabaseClient.for_user(user.token)


def get_admin_db(_admin: CurrentUser = Depends(require_admin)) -> SupabaseClient:
    """Service-role Supabase client for admin-only cross-user operations.

    Owner-scoped RLS means an admin viewing another user's data is never the
    row owner, so admin reads/writes must go through the service-role client
    (bypasses RLS). Authorization is enforced once, here, by ``require_admin``.
    """
    return SupabaseClient()
