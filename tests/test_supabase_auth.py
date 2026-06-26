"""Supabase auth + tier resolution tests (mocked — no live keys required)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

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


def test_resolve_user_tier_prefers_active_subscription():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"tier": "briefing", "status": "active"}]
    )

    with patch("src.db.supabase_auth.get_client", return_value=mock_sb):
        tier = supabase_auth.resolve_user_tier("user-123")
    assert tier == "briefing"


def test_resolve_user_tier_falls_back_to_profile():
    mock_sb = MagicMock()
    subs_chain = mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value
    subs_chain.execute.return_value = MagicMock(data=[])
    profile_chain = mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    profile_chain.execute.return_value = MagicMock(data={"tier": "report"})

    with patch("src.db.supabase_auth.get_client", return_value=mock_sb):
        tier = supabase_auth.resolve_user_tier("user-456")
    assert tier == "report"
