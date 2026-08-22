"""Registration trial + paid-subscription entitlement.

Pure functions only. The LLM never computes CRS, edge, or EV.
Trial is a date window, not a Stripe charge.

Rule (founder, 2026-08-22):
  trial_max_until = created_at + 90 days
  now < trial_max_until  -> effective_tier = agent (max), no charge
  now >= trial_max_until -> effective_tier = free
    unless an active Stripe subscription maps to report/briefing/agent

Day 90 is the drop: created_at + 90d is Free unless paid.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TRIAL_MAX_DAYS = 90
VALID_TIERS = frozenset({"free", "report", "briefing", "agent", "vip", "master"})
PAID_TIERS = frozenset({"report", "briefing", "agent", "vip"})
ACTIVE_SUB_STATUSES = frozenset({"active", "trialing"})
LOCKED_FACTORS = ("S", "B", "C")

# TIER_SPEC interaction levels (caps). Chat 50/day is Agent-only.
TIER_CAPS = {
    "free": {
        "can_read_report": False,
        "can_generate_agents": False,
        "can_chat": False,
        "can_watchlist": False,
        "can_json_api": False,
        "chat_daily_limit": 0,
    },
    "report": {
        "can_read_report": True,
        "can_generate_agents": False,
        "can_chat": False,
        "can_watchlist": False,
        "can_json_api": False,
        "chat_daily_limit": 0,
    },
    "briefing": {
        "can_read_report": True,
        "can_generate_agents": False,
        "can_chat": False,
        "can_watchlist": False,
        "can_json_api": False,
        "chat_daily_limit": 0,
    },
    "agent": {
        "can_read_report": True,
        "can_generate_agents": True,
        "can_chat": True,
        "can_watchlist": True,
        "can_json_api": True,
        "chat_daily_limit": 50,
    },
    "vip": {
        "can_read_report": True,
        "can_generate_agents": True,
        "can_chat": True,
        "can_watchlist": True,
        "can_json_api": True,
        "chat_daily_limit": 50,
    },
    "master": {
        "can_read_report": True,
        "can_generate_agents": True,
        "can_chat": True,
        "can_watchlist": True,
        "can_json_api": True,
        "chat_daily_limit": 50,
    },
}

NEWSLETTER_DEPTH = {
    "free": "summary",
    "report": "report",
    "briefing": "briefing",
    "agent": "agent",
    "vip": "agent",
    "master": "agent",
}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_datetime(value: datetime | str | None) -> datetime | None:
    """Accept datetime or ISO string. Naive values are treated as UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _as_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def normalize_tier(tier: str | None) -> str:
    if not tier:
        return "free"
    t = str(tier).lower().strip()
    if t == "pro":
        return "briefing"
    if t in ("api", "vip"):
        return "agent"
    return t if t in VALID_TIERS else "free"


def trial_max_until(created_at: datetime | str) -> datetime:
    created = parse_datetime(created_at)
    if created is None:
        raise ValueError("created_at is required")
    return created + timedelta(days=TRIAL_MAX_DAYS)


def is_trial_active(created_at: datetime | str | None, now: datetime | None = None) -> bool:
    created = parse_datetime(created_at)
    if created is None:
        return False
    clock = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    return clock < trial_max_until(created)


def subscription_grants_paid(status: str | None, tier: str | None) -> bool:
    if not status or not tier:
        return False
    if str(status).lower() not in ACTIVE_SUB_STATUSES:
        return False
    return normalize_tier(tier) in PAID_TIERS


def effective_tier(
    created_at: datetime | str | None,
    *,
    now: datetime | None = None,
    subscription_tier: str | None = None,
    subscription_status: str | None = None,
    is_master_user: bool = False,
) -> str:
    """Resolve the tier that gates dashboard, API, chat, and newsletter.

    Master email always wins. During the 90-day window the account is Agent
    even with no Stripe object. After the window, an active paid subscription
    wins; otherwise Free.
    """
    if is_master_user:
        return "master"
    clock = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    if is_trial_active(created_at, clock):
        return "agent"
    if subscription_grants_paid(subscription_status, subscription_tier):
        return normalize_tier(subscription_tier)
    return "free"


def entitlement_record(
    created_at: datetime | str | None,
    *,
    now: datetime | None = None,
    subscription_tier: str | None = None,
    subscription_status: str | None = None,
    is_master_user: bool = False,
) -> dict[str, Any]:
    clock = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    created = parse_datetime(created_at)
    until = trial_max_until(created) if created is not None else None
    tier = effective_tier(
        created_at,
        now=clock,
        subscription_tier=subscription_tier,
        subscription_status=subscription_status,
        is_master_user=is_master_user,
    )
    in_trial = bool(created is not None and until is not None and clock < until)
    return {
        "effective_tier": tier,
        "created_at": created.isoformat() if created else None,
        "trial_max_until": until.isoformat() if until else None,
        "trial_active": in_trial and not is_master_user,
        "subscription_tier": normalize_tier(subscription_tier) if subscription_tier else None,
        "subscription_status": (subscription_status or None),
        "asof": clock.isoformat(),
        "source": "entitlement.py",
    }


def tier_caps(tier: str) -> dict[str, Any]:
    return dict(TIER_CAPS.get(normalize_tier(tier), TIER_CAPS["free"]))


def is_paid(tier: str) -> bool:
    t = normalize_tier(tier)
    return t in PAID_TIERS or t == "master"


def newsletter_depth(tier: str) -> str:
    return NEWSLETTER_DEPTH.get(normalize_tier(tier), "summary")


def gate_score(score: dict | None, tier: str) -> dict | None:
    """Free (after trial, no sub) hides S/B/C. Paid + trial-max Agent keep them."""
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
