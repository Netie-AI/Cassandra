"""Supabase GoTrue auth + profile/subscription tier resolution (FastAPI backend)."""
from __future__ import annotations

import os
from typing import Any

import httpx

from .supabase_client import get_client, is_configured

_TIER_RANK = {"agent": 3, "briefing": 2, "report": 1, "free": 0}
_TIER_LABELS = {
    "free": "Free",
    "report": "Report · $4.99",
    "briefing": "Pro Desk · $9.99",
    "agent": "API · $49.99",
}


def _base_url() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/")


def _service_headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def auth_error_message() -> str:
    return "auth_not_configured"


def sign_in(email: str, password: str) -> dict[str, Any]:
    if not is_configured():
        return {"error": auth_error_message()}
    r = httpx.post(
        f"{_base_url()}/auth/v1/token?grant_type=password",
        headers=_service_headers(),
        json={"email": email.strip(), "password": password},
        timeout=30,
    )
    if r.status_code >= 400:
        detail = r.json() if r.content else {}
        return {
            "error": "invalid_credentials",
            "message": detail.get("error_description") or detail.get("msg") or "Sign-in failed.",
        }
    data = r.json()
    user = data.get("user") or {}
    uid = user.get("id")
    if uid:
        ensure_profile(uid, user.get("email") or email)
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "token_type": data.get("token_type", "bearer"),
        "user": _public_user(user) if user else None,
    }


def sign_up(email: str, password: str) -> dict[str, Any]:
    if not is_configured():
        return {"error": auth_error_message()}
    r = httpx.post(
        f"{_base_url()}/auth/v1/signup",
        headers=_service_headers(),
        json={"email": email.strip(), "password": password},
        timeout=30,
    )
    if r.status_code >= 400:
        detail = r.json() if r.content else {}
        return {
            "error": "signup_failed",
            "message": detail.get("error_description") or detail.get("msg") or "Could not create account.",
        }
    data = r.json()
    user = data.get("user") or {}
    uid = user.get("id")
    if uid:
        ensure_profile(uid, user.get("email") or email)
    out: dict[str, Any] = {"ok": True, "user": _public_user(user) if user else None}
    if data.get("access_token"):
        out["access_token"] = data["access_token"]
    if not data.get("access_token"):
        out["message"] = "Check your inbox to confirm your account."
    return out


def ensure_profile(user_id: str, email: str | None) -> None:
    sb = get_client()
    if sb is None or not user_id:
        return
    payload = {"id": user_id, "email": email or "", "tier": "free"}
    try:
        sb.table("profiles").upsert(payload, on_conflict="id").execute()
    except Exception:
        pass


def resolve_user_tier(user_id: str) -> str:
    """Paid subscription wins over profile.tier; highest active tier if multiple."""
    sb = get_client()
    if sb is None or not user_id:
        return "free"
    try:
        subs = (
            sb.table("subscriptions")
            .select("tier,status")
            .eq("user_id", user_id)
            .in_("status", ["active", "trialing"])
            .execute()
        )
        rows = subs.data or []
        if rows:
            best = max(rows, key=lambda row: _TIER_RANK.get(str(row.get("tier", "")).lower(), 0))
            tier = str(best.get("tier", "free")).lower()
            if tier in _TIER_RANK:
                return tier
        row = sb.table("profiles").select("tier").eq("id", user_id).maybe_single().execute()
        data = getattr(row, "data", None) or {}
        tier = str(data.get("tier", "free")).lower() if isinstance(data, dict) else "free"
        return tier if tier in _TIER_RANK else "free"
    except Exception:
        return "free"


def user_from_token(authorization: str | None) -> dict[str, Any] | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    if not is_configured():
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
    except Exception:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    email = payload.get("email")
    tier = resolve_user_tier(str(user_id))
    sb = get_client()
    display_name = None
    if sb is not None:
        try:
            row = sb.table("profiles").select("email,display_name,tier").eq("id", user_id).maybe_single().execute()
            data = getattr(row, "data", None) or {}
            if isinstance(data, dict):
                email = data.get("email") or email
                display_name = data.get("display_name")
        except Exception:
            pass
    return {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "tier": tier,
        "tier_label": _TIER_LABELS.get(tier, tier),
    }


def apply_subscription(
    *,
    user_id: str,
    tier: str,
    provider: str,
    external_id: str,
    status: str = "active",
) -> None:
    """Upsert subscription row and sync profiles.tier (Stripe/Billplz webhooks)."""
    sb = get_client()
    if sb is None:
        raise RuntimeError("Supabase not configured")
    tier = tier.lower()
    if tier not in ("report", "briefing", "agent"):
        raise ValueError(f"Invalid paid tier: {tier}")
    status = status.lower()
    if status not in ("trialing", "active", "past_due", "canceled"):
        raise ValueError(f"Invalid subscription status: {status}")
    sb.table("subscriptions").upsert(
        {
            "user_id": user_id,
            "provider": provider,
            "external_id": external_id,
            "tier": tier,
            "status": status,
        },
        on_conflict="provider,external_id",
    ).execute()
    profile_tier = tier if status in ("active", "trialing") else "free"
    sb.table("profiles").update({"tier": profile_tier}).eq("id", user_id).execute()


def find_user_id_by_email(email: str) -> str | None:
    sb = get_client()
    if sb is None:
        return None
    try:
        row = sb.table("profiles").select("id").eq("email", email.strip().lower()).maybe_single().execute()
        data = getattr(row, "data", None) or {}
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
    except Exception:
        pass
    return None


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    uid = user.get("id")
    tier = resolve_user_tier(str(uid)) if uid else "free"
    return {
        "id": uid,
        "email": user.get("email"),
        "tier": tier,
        "tier_label": _TIER_LABELS.get(tier, tier),
    }
