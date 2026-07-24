"""One-off script: promote a user to admin.

Usage: uv run python scripts/promote_admin.py <user-email>

Requires SUPABASE_URL and SUPABASE_KEY (service role) in .env. There is no
self-service path to admin — this script, run manually with the service-role
key, is the only way an account becomes an admin.
"""

from __future__ import annotations

import sys

from job_agent.config import get_settings
from job_agent.db.client import SupabaseClient


def promote(email: str) -> None:
    db = SupabaseClient()
    users = db.raw.auth.admin.list_users()
    match = next((u for u in users if u.email == email), None)
    if match is None:
        raise SystemExit(f"No user found with email {email!r}")
    db.raw.auth.admin.update_user_by_id(match.id, {"app_metadata": {"role": "admin"}})
    print(f"Promoted {email} ({match.id}) to admin.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run python scripts/promote_admin.py <user-email>")
    get_settings().require_live_credentials()
    promote(sys.argv[1])
