"""Digest unsubscribe token tests."""
from __future__ import annotations

from src.store import list_digest_recipients, save_digest_subscriber, unsubscribe_digest


def test_unsubscribe_token_roundtrip():
    email = "unsub-test@netie.ai"
    _, confirmed, token = save_digest_subscriber(email, "test")
    assert confirmed
    assert token
    recs = [r for r in list_digest_recipients() if r["email"] == email]
    assert recs
    assert recs[0]["unsub_token"]
    out = unsubscribe_digest(token)
    assert out == email
    assert unsubscribe_digest(token) is None
