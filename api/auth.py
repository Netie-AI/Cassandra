"""Tier lookup + score access gates."""
from __future__ import annotations

from fastapi import Header

VALID_TIERS = frozenset({"free", "report", "briefing", "agent"})
PAID_TIERS = frozenset({"report", "briefing", "agent"})
LOCKED_FACTORS = ("S", "B", "C")
FREE_DELAY_DAYS = 2
FIRST_SUB_TRIAL_DAYS = 7


def get_tier(jwt_token: str | None = None) -> str:
    """Direct JWT tier lookup (smoke tests / CLI). Returns 'free' when auth missing or invalid."""
    if not jwt_token:
        return "free"
    auth = jwt_token if jwt_token.startswith("Bearer ") else f"Bearer {jwt_token}"
    try:
        from src.db.supabase_client import tier_from_jwt
        tier = tier_from_jwt(auth)
        return tier if tier and tier in VALID_TIERS else "free"
    except Exception:
        return "free"


def get_user_tier(
    authorization: str | None = Header(default=None),
    x_tier: str | None = Header(default=None, alias="X-Tier"),
) -> str:
    """Return user tier. Dev: pass X-Tier header. Prod: Supabase JWT when configured."""
    if x_tier and x_tier.lower() in VALID_TIERS:
        return x_tier.lower()
    try:
        from src.db.supabase_client import tier_from_jwt
        jwt_tier = tier_from_jwt(authorization)
        if jwt_tier and jwt_tier in VALID_TIERS:
            return jwt_tier
    except Exception:
        pass
    return "free"


def is_paid(tier: str) -> bool:
    return tier in PAID_TIERS


def resolve_score_dict(tier: str) -> dict | None:
    """Free tier gets score from FREE_DELAY_DAYS ago; paid gets latest."""
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


def gate_score(score: dict | None, tier: str) -> dict | None:
    if not score:
        return score
    if tier in PAID_TIERS:
        return score
    out = dict(score)
    factors = dict(out.get("factors") or {})
    for key in LOCKED_FACTORS:
        if key in factors:
            factors[key] = None
    out["factors"] = factors
    return out


def subscription_checkout_options(tier: str, *, is_first_subscription: bool = True) -> dict:
    """Payment checkout metadata — 7-day trial on first paid subscription."""
    tier = tier.lower()
    if tier not in VALID_TIERS:
        tier = "report"
    out: dict = {"tier": tier, "trial_days": 0, "first_subscriber_trial": False}
    if is_first_subscription and tier in PAID_TIERS:
        out["trial_days"] = FIRST_SUB_TRIAL_DAYS
        out["first_subscriber_trial"] = True
    return out
