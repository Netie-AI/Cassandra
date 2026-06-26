"""Optional Supabase client — returns None when env not configured (SQLite fallback)."""
from __future__ import annotations

import os
from typing import Any

_client: Any = None


def is_configured() -> bool:
    """True when URL + service role + JWT secret are all set (live auth path)."""
    return bool(
        os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        and os.getenv("SUPABASE_JWT_SECRET")
    )


def get_client():
    """Lazy Supabase client (service role — pipeline/backend only)."""
    global _client
    if _client is not None:
        return _client
    if not is_configured():
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    _client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    return _client


def tier_from_jwt(authorization: str | None) -> str | None:
    """Resolve tier from Supabase JWT (subscriptions + profile). Returns None if invalid."""
    from .supabase_auth import user_from_token

    user = user_from_token(authorization)
    return user.get("tier") if user else None
