"""Supabase GoTrue auth + profile/subscription tier resolution (FastAPI backend)."""
from __future__ import annotations

import os
from typing import Any

import httpx

from src.entitlement import entitlement_record

from .supabase_client import get_client, is_configured

_TIER_RANK = {"agent": 3, "briefing": 2, "report": 1, "free": 0}
_TIER_LABELS = {
    "free": "Free",
    "report": "Report · $4.99",
    "briefing": "The Briefing · $9.99",
    "agent": "The Agent · $49.99",
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


def _best_subscription(user_id: str) -> tuple[str | None, str | None]:
    sb = get_client()
    if sb is None or not user_id:
        return None, None
    try:
        subs = (
            sb.table("subscriptions")
            .select("tier,status")
            .eq("user_id", user_id)
            .in_("status", ["active", "trialing"])
            .execute()
        )
        rows = subs.data or []
        if not rows:
            return None, None
        best = max(rows, key=lambda row: _TIER_RANK.get(str(row.get("tier", "")).lower(), 0))
        return str(best.get("tier") or ""), str(best.get("status") or "")
    except Exception:
        return None, None


def _profile_created_at(user_id: str) -> str | None:
    sb = get_client()
    if sb is None or not user_id:
        return None
    try:
        row = (
            sb.table("profiles")
            .select("created_at,tier")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        data = getattr(row, "data", None) or {}
        if isinstance(data, dict):
            return data.get("created_at")
    except Exception:
        return None
    return None


def account_snapshot(user_id: str, email: str | None = None) -> dict:
    """created_at + best Stripe sub. Used by entitlement (trial_max_until)."""
    sub_tier, sub_status = _best_subscription(user_id)
    created = _profile_created_at(user_id)
    master = (os.getenv("MASTER_EMAIL") or "").strip().lower()
    is_master_user = bool(master and email and email.strip().lower() == master)
    rec = entitlement_record(
        created,
        subscription_tier=sub_tier,
        subscription_status=sub_status,
        is_master_user=is_master_user,
    )
    rec["user_id"] = user_id
    rec["email"] = email
    rec["is_master"] = is_master_user
    rec["subscription_tier"] = sub_tier
    rec["subscription_status"] = sub_status
    rec["created_at"] = created or rec.get("created_at")
    return rec


def account_from_token(authorization: str | None) -> dict:
    """JWT -> account snapshot for entitlement. Empty dict when auth is stub."""
    user = user_from_token(authorization)
    if not user:
        return {}
    return {
        "created_at": user.get("created_at"),
        "subscription_tier": user.get("subscription_tier"),
        "subscription_status": user.get("subscription_status"),
        "is_master": bool(user.get("is_master")),
        "user_id": user.get("id"),
        "email": user.get("email"),
    }


def resolve_user_tier(user_id: str) -> str:
    """Effective tier: 90-day Agent trial, then Free unless Stripe is active."""
    snap = account_snapshot(user_id)
    return str(snap.get("effective_tier") or "free")


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
    sb = get_client()
    display_name = None
    created_at = payload.get("created_at")
    if sb is not None:
        try:
            row = (
                sb.table("profiles")
                .select("email,display_name,tier,created_at")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            data = getattr(row, "data", None) or {}
            if isinstance(data, dict):
                email = data.get("email") or email
                display_name = data.get("display_name")
                created_at = data.get("created_at") or created_at
        except Exception:
            pass
    snap = account_snapshot(str(user_id), email)
    if created_at and not snap.get("created_at"):
        snap = entitlement_record(
            created_at,
            subscription_tier=snap.get("subscription_tier"),
            subscription_status=snap.get("subscription_status"),
            is_master_user=bool(snap.get("is_master")),
        )
        snap["subscription_tier"] = snap.get("subscription_tier")
    tier = str(snap.get("effective_tier") or "free")
    return {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "tier": tier,
        "tier_label": _TIER_LABELS.get(tier, tier),
        "created_at": snap.get("created_at") or created_at,
        "trial_max_until": snap.get("trial_max_until"),
        "trial_active": snap.get("trial_active"),
        "subscription_tier": snap.get("subscription_tier"),
        "subscription_status": snap.get("subscription_status"),
        "is_master": bool(snap.get("is_master")),
    }


def apply_subscription(
    *,
    user_id: str,
    tier: str,
    provider: str,
    external_id: str,
    status: str = "active",
    stripe_customer_id: str | None = None,
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
    patch: dict[str, Any] = {"tier": profile_tier}
    if stripe_customer_id:
        patch["stripe_customer_id"] = stripe_customer_id
    sb.table("profiles").update(patch).eq("id", user_id).execute()


def stripe_customer_id_for_user(user_id: str) -> str | None:
    sb = get_client()
    if sb is None or not user_id:
        return None
    try:
        row = (
            sb.table("profiles")
            .select("stripe_customer_id")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        data = getattr(row, "data", None) or {}
        cid = data.get("stripe_customer_id") if isinstance(data, dict) else None
        return str(cid) if cid else None
    except Exception:
        return None


def account_for_email(email: str) -> dict:
    """Resolve entitlement for a newsletter recipient. Unknown email -> Free."""
    uid = find_user_id_by_email(email)
    if not uid:
        rec = entitlement_record(None)
        rec["email"] = email
        return rec
    return account_snapshot(uid, email)


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
    email = user.get("email")
    snap = account_snapshot(str(uid), email) if uid else {}
    tier = str(snap.get("effective_tier") or "free")
    return {
        "id": uid,
        "email": email,
        "tier": tier,
        "tier_label": _TIER_LABELS.get(tier, tier),
        "created_at": snap.get("created_at"),
        "trial_max_until": snap.get("trial_max_until"),
        "trial_active": snap.get("trial_active"),
    }
