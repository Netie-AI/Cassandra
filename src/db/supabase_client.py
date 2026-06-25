"""Optional Supabase client — returns None when env not configured (SQLite fallback)."""
from __future__ import annotations

import os
from typing import Any

_client: Any = None


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


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
    """Resolve tier from Supabase JWT. Returns None if not configured or invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    if not os.getenv("SUPABASE_JWT_SECRET"):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        import jwt
        payload = jwt.decode(
            token,
            os.environ["SUPABASE_JWT_SECRET"],
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        sb = get_client()
        if sb is None:
            return None
        row = sb.table("profiles").select("tier").eq("id", user_id).maybe_single().execute()
        data = getattr(row, "data", None) or {}
        tier = data.get("tier") if isinstance(data, dict) else None
        return str(tier).lower() if tier else "free"
    except Exception:
        return None
