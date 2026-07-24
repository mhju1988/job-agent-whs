"""Tests for the API auth dependency — no live calls."""

from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException

from job_agent.api.deps import _decode_token
from job_agent.config import Settings

SECRET = "super-secret"


def _token(sub: str = "u-1", aud: str = "authenticated") -> str:
    return jwt.encode({"sub": sub, "aud": aud}, SECRET, algorithm="HS256")


def test_decode_valid_token_returns_user_id() -> None:
    s = Settings(supabase_jwt_secret=SECRET)
    assert _decode_token(_token(), s) == "u-1"


def test_decode_rejects_bad_signature() -> None:
    s = Settings(supabase_jwt_secret=SECRET)
    bad = jwt.encode({"sub": "u-1", "aud": "authenticated"}, "wrong", algorithm="HS256")
    with pytest.raises(HTTPException) as ei:
        _decode_token(bad, s)
    assert ei.value.status_code == 401


def test_decode_rejects_wrong_audience() -> None:
    s = Settings(supabase_jwt_secret=SECRET)
    tok = jwt.encode({"sub": "u-1", "aud": "anon"}, SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as ei:
        _decode_token(tok, s)
    assert ei.value.status_code == 401


def test_decode_missing_secret_is_500() -> None:
    s = Settings(supabase_jwt_secret="")
    with pytest.raises(HTTPException) as ei:
        _decode_token(_token(), s)
    assert ei.value.status_code == 500


def test_decode_es256_token_via_jwks(monkeypatch) -> None:
    """Asymmetric (ES256) tokens verify against the project JWKS (mocked client)."""
    from types import SimpleNamespace

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from job_agent.api import deps

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = priv.public_key()
    es_token = jwt.encode(
        {"sub": "u-7", "aud": "authenticated"}, priv_pem, algorithm="ES256"
    )

    # Patch the JWKS client so no network call happens; return our public key.
    fake_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=pub)
    )
    monkeypatch.setattr(deps, "_jwks_client", lambda _url: fake_client)

    s = Settings(supabase_url="https://proj.supabase.co", supabase_jwt_secret="")
    assert _decode_token(es_token, s) == "u-7"


def test_get_current_user_defaults_role_to_user(monkeypatch) -> None:
    from job_agent.api import deps

    monkeypatch.setattr(deps, "_decode_claims", lambda _t, _s: {"sub": "u-1"})
    user = deps.get_current_user(authorization="Bearer tok", settings=Settings())
    assert user.role == "user"


def test_get_current_user_reads_admin_role_from_app_metadata(monkeypatch) -> None:
    from job_agent.api import deps

    monkeypatch.setattr(
        deps,
        "_decode_claims",
        lambda _t, _s: {"sub": "u-1", "app_metadata": {"role": "admin"}},
    )
    user = deps.get_current_user(authorization="Bearer tok", settings=Settings())
    assert user.role == "admin"


def test_get_current_user_ignores_non_admin_role_values(monkeypatch) -> None:
    from job_agent.api import deps

    monkeypatch.setattr(
        deps,
        "_decode_claims",
        lambda _t, _s: {"sub": "u-1", "app_metadata": {"role": "superuser"}},
    )
    user = deps.get_current_user(authorization="Bearer tok", settings=Settings())
    assert user.role == "user"


def test_require_admin_passes_through_admin() -> None:
    from job_agent.api.deps import CurrentUser, require_admin

    admin = CurrentUser(user_id="u-1", token="t", role="admin")
    assert require_admin(user=admin) is admin


def test_require_admin_rejects_regular_user() -> None:
    from job_agent.api.deps import CurrentUser, require_admin

    with pytest.raises(HTTPException) as ei:
        require_admin(user=CurrentUser(user_id="u-1", token="t", role="user"))
    assert ei.value.status_code == 403
