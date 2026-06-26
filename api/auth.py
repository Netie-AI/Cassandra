"""Tier lookup + score access gates."""
from __future__ import annotations

import os

from fastapi import Header

VALID_TIERS = frozenset({"free", "report", "briefing", "agent", "vip", "master"})
PAID_TIERS = frozenset({"report", "briefing", "agent", "vip"})
LOCKED_FACTORS = ("S", "B", "C")
FREE_DELAY_DAYS = 2
FIRST_SUB_TRIAL_DAYS = 7

TIER_CAPS = {
    "free": {"can_read_report": False, "can_generate_agents": False, "can_chat": False},
    "report": {"can_read_report": True, "can_generate_agents": False, "can_chat": False},
    "briefing": {"can_read_report": True, "can_generate_agents": False, "can_chat": True},
    "agent": {"can_read_report": True, "can_generate_agents": True, "can_chat": True},
    "vip": {"can_read_report": True, "can_generate_agents": True, "can_chat": True},
    "master": {"can_read_report": True, "can_generate_agents": True, "can_chat": True},
}

TIER_DISPLAY = {
    "free": "Free",
    "report": "Report · $4.99",
    "briefing": "Pro Desk · $9.99",
    "agent": "VIP · $49.99",
    "vip": "VIP · $49.99",
    "master": "Master",
}


def normalize_tier(tier: str | None) -> str:
    """Map legacy/internal tier ids to canonical keys."""
    if not tier:
        return "free"
    t = tier.lower()
    if t == "pro":
        return "briefing"
    if t in ("api", "vip"):
        return "agent"
    return t if t in VALID_TIERS else "free"


def tier_caps(tier: str) -> dict[str, bool]:
    return dict(TIER_CAPS.get(normalize_tier(tier), TIER_CAPS["free"]))


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


def effective_tier(jwt_token: str | None, header_tier: str | None = None) -> str:
    """Resolve tier; master email always maps to master caps."""
    if is_master(jwt_token):
        return "master"
    if header_tier and _x_tier_allowed():
        ht = normalize_tier(header_tier)
        if ht in VALID_TIERS:
            if ht == "master" and os.getenv("ALLOW_X_TIER_MASTER", "").lower() != "true":
                pass
            else:
                return ht
    return normalize_tier(get_tier(jwt_token))


def get_tier(jwt_token: str | None = None) -> str:
    """Direct JWT tier lookup (smoke tests / CLI). Returns 'free' when auth missing or invalid."""
    if not jwt_token:
        return "free"
    auth = jwt_token if jwt_token.startswith("Bearer ") else f"Bearer {jwt_token}"
    try:
        from src.db.supabase_client import tier_from_jwt
        tier = tier_from_jwt(auth)
        return normalize_tier(tier) if tier else "free"
    except Exception:
        return "free"


def get_user_tier(
    authorization: str | None = Header(default=None),
    x_tier: str | None = Header(default=None, alias="X-Tier"),
) -> str:
    """Return user tier. Dev: pass X-Tier header. Prod: Supabase JWT when configured."""
    return effective_tier(authorization, x_tier)


def is_paid(tier: str) -> bool:
    return tier in PAID_TIERS or tier == "master"


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
    if is_paid(tier):
        return score
    out = dict(score)
    factors = dict(out.get("factors") or {})
    for key in LOCKED_FACTORS:
        if key in factors:
            factors[key] = None
    out["factors"] = factors
    return out


def subscription_checkout_options(tier: str, *, is_first_subscription: bool = True) -> dict:
    """Payment checkout metadata — 7-day trial on first paid subscription (not VIP)."""
    tier = normalize_tier(tier)
    if tier not in VALID_TIERS:
        tier = "report"
    out: dict = {"tier": tier, "trial_days": 0, "first_subscriber_trial": False}
    if tier == "agent":
        return out
    if is_first_subscription and tier in PAID_TIERS and tier != "agent":
        out["trial_days"] = FIRST_SUB_TRIAL_DAYS
        out["first_subscriber_trial"] = True
    return out
