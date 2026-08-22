"""Tier lookup + score access gates. Effective tier comes from entitlement.py."""
from __future__ import annotations

import os

from fastapi import Header

from src.entitlement import (
    LOCKED_FACTORS,
    PAID_TIERS,
    VALID_TIERS,
    effective_tier as compute_effective_tier,
    entitlement_record,
    gate_score,
    is_paid,
    is_trial_active,
    newsletter_depth,
    normalize_tier,
    parse_datetime,
    tier_caps,
    trial_max_until,
)

# Re-export so existing imports keep working.
FREE_DELAY_DAYS = 2
TRIAL_MAX_DAYS = 90
# Registration trial is 90 days of Agent. Stripe checkout has no trial days
# and does not auto-convert to a paid plan.
FIRST_SUB_TRIAL_DAYS = 0

TIER_DISPLAY = {
    "free": "Free",
    "report": "Report · $4.99",
    "briefing": "The Briefing · $9.99",
    "agent": "The Agent · $49.99",
    "vip": "The Agent · $49.99",
    "master": "Master",
}


def is_master(jwt_token: str | None) -> bool:
    """True when bearer token belongs to MASTER_EMAIL."""
    master = os.getenv("MASTER_EMAIL", "").strip().lower()
    if not master or not jwt_token:
        return False
    auth = jwt_token if jwt_token.startswith("Bearer ") else f"Bearer {jwt_token}"
    try:
        from src.db.supabase_auth import user_from_token

        user = user_from_token(auth)
        return bool(user and str(user.get("email", "")).lower() == master)
    except Exception:
        return False


def _x_tier_allowed() -> bool:
    flag = os.getenv("ALLOW_X_TIER", "").strip().lower()
    if flag == "true":
        return True
    if flag == "false":
        return False
    try:
        from src.db.supabase_client import is_configured

        return not is_configured()
    except Exception:
        return True


def _account_from_jwt(jwt_token: str | None) -> dict:
    """Pull created_at + stored subscription from JWT/profile. Empty if stub."""
    if not jwt_token:
        return {}
    auth = jwt_token if jwt_token.startswith("Bearer ") else f"Bearer {jwt_token}"
    try:
        from src.db.supabase_auth import account_from_token

        return account_from_token(auth) or {}
    except Exception:
        return {}


def effective_tier(jwt_token: str | None, header_tier: str | None = None) -> str:
    """Resolve the tier that gates dashboard, API, chat, and newsletter."""
    if is_master(jwt_token):
        return "master"
    if header_tier and _x_tier_allowed():
        ht = normalize_tier(header_tier)
        if ht in VALID_TIERS:
            if ht == "master" and os.getenv("ALLOW_X_TIER_MASTER", "").lower() != "true":
                pass
            else:
                return ht
    account = _account_from_jwt(jwt_token)
    if not account:
        return "free"
    return compute_effective_tier(
        account.get("created_at"),
        subscription_tier=account.get("subscription_tier"),
        subscription_status=account.get("subscription_status"),
        is_master_user=bool(account.get("is_master")),
    )


def get_tier(jwt_token: str | None = None) -> str:
    """Direct JWT entitlement lookup. Returns 'free' when auth missing or invalid."""
    return effective_tier(jwt_token, None)


def get_user_tier(
    authorization: str | None = Header(default=None),
    x_tier: str | None = Header(default=None, alias="X-Tier"),
) -> str:
    """Return effective tier. Dev: X-Tier header. Prod: entitlement from registration + Stripe."""
    return effective_tier(authorization, x_tier)


def resolve_score_dict(tier: str) -> dict | None:
    """Free tier gets score from FREE_DELAY_DAYS ago; paid/trial-max gets latest."""
    from src.store import latest_score, score_by_offset_days

    if is_paid(tier):
        raw = latest_score()
    else:
        raw = score_by_offset_days(FREE_DELAY_DAYS) or latest_score()
    if not raw:
        return None
    out = dict(raw)
    if not is_paid(tier):
        latest = latest_score()
        if latest and latest.get("asof") != out.get("asof"):
            out["delayed"] = True
            out["delay_days"] = FREE_DELAY_DAYS
    return out


def subscription_checkout_options(tier: str, *, is_first_subscription: bool = True) -> dict:
    """Checkout metadata. Registration already granted 90 days of Agent. No Stripe trial."""
    del is_first_subscription  # kept for API compatibility
    tier = normalize_tier(tier)
    if tier not in VALID_TIERS:
        tier = "report"
    return {
        "tier": tier,
        "trial_days": 0,
        "first_subscriber_trial": False,
        "registration_trial_days": TRIAL_MAX_DAYS,
        "trial_message": (
            "Every new account gets The Agent free for 3 months from registration. "
            "On day 90 you drop to Free. No charge during the trial. "
            "Subscribe after that if you want Report, Briefing, or Agent."
        ),
        "auto_converts": False,
    }


def entitlement_for_request(jwt_token: str | None = None) -> dict:
    account = _account_from_jwt(jwt_token)
    return entitlement_record(
        account.get("created_at"),
        subscription_tier=account.get("subscription_tier"),
        subscription_status=account.get("subscription_status"),
        is_master_user=bool(account.get("is_master")),
    )


__all__ = [
    "FREE_DELAY_DAYS",
    "FIRST_SUB_TRIAL_DAYS",
    "LOCKED_FACTORS",
    "PAID_TIERS",
    "TRIAL_MAX_DAYS",
    "TIER_DISPLAY",
    "VALID_TIERS",
    "effective_tier",
    "entitlement_for_request",
    "entitlement_record",
    "gate_score",
    "get_tier",
    "get_user_tier",
    "is_master",
    "is_paid",
    "is_trial_active",
    "newsletter_depth",
    "normalize_tier",
    "parse_datetime",
    "resolve_score_dict",
    "subscription_checkout_options",
    "tier_caps",
    "trial_max_until",
]
