"""Signed Stripe webhook fixture tests (no live secret required)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import stripe

from src.billing import construct_event, map_stripe_event

FIXTURES = Path(__file__).parent / "fixtures" / "stripe"
TEST_WHSEC = "whsec_test_cassandra_fixture_not_a_real_secret"


def _signed(name: str) -> tuple[bytes, str]:
    payload = (FIXTURES / name).read_bytes()
    header = stripe.Webhook.generate_test_header_string(
        payload=payload.decode("utf-8"),
        secret=TEST_WHSEC,
    )
    return payload, header


def test_construct_event_accepts_signed_checkout_fixture():
    payload, header = _signed("checkout.session.completed.json")
    event = construct_event(payload, header, TEST_WHSEC)
    assert event["type"] == "checkout.session.completed"
    mapped = map_stripe_event(event)
    assert mapped["action"] == "upsert"
    assert mapped["tier"] == "report"
    assert mapped["user_id"] == "user-abc"
    assert mapped["status"] == "active"


def test_construct_event_rejects_bad_signature():
    payload, _ = _signed("invoice.paid.json")
    with pytest.raises(Exception):
        construct_event(payload, "t=1,v1=deadbeef", TEST_WHSEC)


def test_invoice_paid_maps_to_briefing():
    payload, header = _signed("invoice.paid.json")
    event = construct_event(payload, header, TEST_WHSEC)
    mapped = map_stripe_event(event)
    assert mapped["etype"] == "invoice.paid"
    assert mapped["tier"] == "briefing"
    assert mapped["user_id"] == "user-def"


def test_subscription_deleted_maps_to_cancel():
    payload, header = _signed("customer.subscription.deleted.json")
    event = construct_event(payload, header, TEST_WHSEC)
    mapped = map_stripe_event(event)
    assert mapped["action"] == "cancel"
    assert mapped["status"] == "canceled"
    assert mapped["user_id"] == "user-ghi"


def test_price_id_fallback_when_metadata_missing(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_AGENT", "price_test_agent")
    event = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_x",
                "customer_email": "x@y.com",
                "metadata": {"product_line": "cassandra"},
                "lines": {"data": [{"price": {"id": "price_test_agent"}}]},
            }
        },
    }
    mapped = map_stripe_event(event)
    assert mapped["tier"] == "agent"


def test_fastapi_webhook_accepts_signed_fixture(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", TEST_WHSEC)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    payload, header = _signed("checkout.session.completed.json")
    with patch("src.billing.apply_mapped_event", return_value={"applied": True, "action": "upsert"}):
        client = TestClient(app)
        r = client.post(
            "/api/webhooks/stripe",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_apply_mapped_event_calls_apply_subscription():
    from src.billing import apply_mapped_event

    mapped = {
        "action": "upsert",
        "tier": "report",
        "user_id": "user-abc",
        "status": "active",
        "external_id": "sub_1",
        "email": "trial@example.com",
    }
    with patch("src.db.supabase_auth.apply_subscription") as apply:
        out = apply_mapped_event(mapped)
    apply.assert_called_once()
    assert out["applied"] is True
