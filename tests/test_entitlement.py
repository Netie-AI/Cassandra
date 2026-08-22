"""Freeze time across day 89 vs day 91 of the registration trial."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.entitlement import (
    TRIAL_MAX_DAYS,
    effective_tier,
    entitlement_record,
    gate_score,
    is_trial_active,
    newsletter_depth,
    tier_caps,
    trial_max_until,
)

CREATED = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_trial_max_until_is_created_plus_90():
    assert TRIAL_MAX_DAYS == 90
    assert trial_max_until(CREATED) == CREATED + timedelta(days=90)


def test_day_89_still_agent():
    now = CREATED + timedelta(days=89)
    assert is_trial_active(CREATED, now) is True
    assert effective_tier(CREATED, now=now) == "agent"
    rec = entitlement_record(CREATED, now=now)
    assert rec["trial_active"] is True
    assert rec["effective_tier"] == "agent"


def test_day_90_drops_to_free():
    now = CREATED + timedelta(days=90)
    assert is_trial_active(CREATED, now) is False
    assert effective_tier(CREATED, now=now) == "free"


def test_day_91_is_free_without_subscription():
    now = CREATED + timedelta(days=91)
    assert is_trial_active(CREATED, now) is False
    assert effective_tier(CREATED, now=now) == "free"
    rec = entitlement_record(CREATED, now=now)
    assert rec["trial_active"] is False
    assert rec["effective_tier"] == "free"


def test_day_91_paid_report_wins():
    now = CREATED + timedelta(days=91)
    assert (
        effective_tier(
            CREATED,
            now=now,
            subscription_tier="report",
            subscription_status="active",
        )
        == "report"
    )


def test_day_91_canceled_sub_is_free():
    now = CREATED + timedelta(days=91)
    assert (
        effective_tier(
            CREATED,
            now=now,
            subscription_tier="agent",
            subscription_status="canceled",
        )
        == "free"
    )


def test_day_89_stays_agent_even_if_free_profile():
    now = CREATED + timedelta(days=89)
    assert (
        effective_tier(
            CREATED,
            now=now,
            subscription_tier="free",
            subscription_status=None,
        )
        == "agent"
    )


def test_legacy_price_aliases_normalize():
    now = CREATED + timedelta(days=91)
    assert (
        effective_tier(
            CREATED,
            now=now,
            subscription_tier="pro",
            subscription_status="active",
        )
        == "briefing"
    )
    assert (
        effective_tier(
            CREATED,
            now=now,
            subscription_tier="api",
            subscription_status="trialing",
        )
        == "agent"
    )


def test_anonymous_without_created_at_is_free():
    assert effective_tier(None, now=CREATED) == "free"


def test_master_bypasses_trial_window():
    now = CREATED + timedelta(days=91)
    assert effective_tier(CREATED, now=now, is_master_user=True) == "master"


def test_gate_score_hides_sbc_for_free_keeps_for_agent():
    raw = {"crs": 40, "factors": {"L": 0.5, "V": 0.4, "S": 0.7, "B": 0.6, "C": 0.5}}
    free = gate_score(raw, "free")
    assert free["factors"]["S"] is None
    assert free["factors"]["B"] is None
    assert free["factors"]["C"] is None
    assert free["factors"]["L"] == 0.5
    agent = gate_score(raw, "agent")
    assert agent["factors"]["S"] == 0.7


def test_agent_caps_include_watchlist_and_chat_50():
    caps = tier_caps("agent")
    assert caps["can_watchlist"] is True
    assert caps["can_chat"] is True
    assert caps["chat_daily_limit"] == 50
    assert newsletter_depth("free") == "summary"
    assert newsletter_depth("briefing") == "briefing"
    assert newsletter_depth("agent") == "agent"
