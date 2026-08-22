"""Supabase auth + tier resolution tests (mocked — no live keys required)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.db import supabase_auth


def test_get_tier_returns_free_without_token():
    from api.auth import get_tier

    assert get_tier(None) == "free"
    assert get_tier("") == "free"


def test_auth_not_configured_when_keys_missing():
    with patch.dict(os.environ, {"SUPABASE_URL": "https://x.supabase.co"}, clear=False):
        os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
        os.environ.pop("SUPABASE_JWT_SECRET", None)
        out = supabase_auth.sign_in("a@b.com", "password123")
        assert out["error"] == "auth_not_configured"


def test_resolve_user_tier_prefers_trial_when_created_recent():
    created = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with patch("src.db.supabase_auth._best_subscription", return_value=(None, None)):
        with patch("src.db.supabase_auth._profile_created_at", return_value=created):
            assert supabase_auth.resolve_user_tier("user-123") == "agent"


def test_resolve_user_tier_paid_after_trial():
    created = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    with patch("src.db.supabase_auth._best_subscription", return_value=("briefing", "active")):
        with patch("src.db.supabase_auth._profile_created_at", return_value=created):
            assert supabase_auth.resolve_user_tier("user-123") == "briefing"


def test_resolve_user_tier_free_after_trial_without_sub():
    created = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    with patch("src.db.supabase_auth._best_subscription", return_value=(None, None)):
        with patch("src.db.supabase_auth._profile_created_at", return_value=created):
            assert supabase_auth.resolve_user_tier("user-456") == "free"
