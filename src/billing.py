"""Stripe Checkout, Customer Portal, and signed webhook mapping.

Keys come from env only. Never log secrets. No execution / no auto-trade.
Registration trial is NOT a Stripe trial: Checkout charges only after the
user chooses a paid plan. Trial does not auto-convert to a paid subscription.
"""
from __future__ import annotations

import os
from typing import Any

from .entitlement import normalize_tier

PRODUCT_LINE = "cassandra"
PAID_INTERNAL_TIERS = ("report", "briefing", "agent")

# Public checkout/portal paths used by the pricing page (not secrets).
CHECKOUT_PATH = "/api/billing/checkout"
PORTAL_PATH = "/api/billing/portal"


class BillingError(RuntimeError):
    """User-facing billing failure (missing config, unknown tier, etc.)."""


def stripe_secret_key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()


def webhook_secret() -> str:
    return (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()


def is_configured() -> bool:
    return bool(stripe_secret_key())


def price_id_for_tier(tier: str) -> str:
    t = normalize_tier(tier)
    mapping = {
        "report": os.getenv("STRIPE_PRICE_REPORT", ""),
        "briefing": os.getenv("STRIPE_PRICE_BRIEFING") or os.getenv("STRIPE_PRICE_PRO", ""),
        "agent": os.getenv("STRIPE_PRICE_AGENT") or os.getenv("STRIPE_PRICE_API", ""),
    }
    price = (mapping.get(t) or "").strip()
    if not price:
        raise BillingError(f"No Stripe price ID configured for tier={t}")
    return price


def tier_from_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    mapping = {
        (os.getenv("STRIPE_PRICE_REPORT") or "").strip(): "report",
        (os.getenv("STRIPE_PRICE_PRO") or "").strip(): "briefing",
        (os.getenv("STRIPE_PRICE_BRIEFING") or "").strip(): "briefing",
        (os.getenv("STRIPE_PRICE_API") or "").strip(): "agent",
        (os.getenv("STRIPE_PRICE_AGENT") or "").strip(): "agent",
    }
    return mapping.get(price_id)


def tier_from_metadata(meta: dict | None) -> str | None:
    if not meta:
        return None
    raw = meta.get("tier") or meta.get("plan") or meta.get("internal_tier")
    if not raw:
        return None
    t = normalize_tier(str(raw))
    return t if t in PAID_INTERNAL_TIERS else None


def is_cassandra_event(meta: dict | None) -> bool:
    line = str((meta or {}).get("product_line") or "").lower()
    return not line or line == PRODUCT_LINE


def construct_event(payload: bytes | str, sig_header: str, secret: str | None = None) -> dict:
    """Verify Stripe-Signature and return the event dict. Raises ValueError on fail."""
    import stripe

    sec = (secret if secret is not None else webhook_secret()).strip()
    if not sec:
        raise BillingError("STRIPE_WEBHOOK_SECRET not set")
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = payload
    key = stripe_secret_key()
    if key:
        stripe.api_key = key
    event = stripe.Webhook.construct_event(payload_bytes, sig_header, sec)
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return dict(event)


def _site_base() -> str:
    return (os.getenv("PUBLIC_SITE_URL") or "https://crash.netie.ai").rstrip("/")


def create_checkout_session(
    *,
    tier: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
    customer_email: str | None = None,
    user_id: str | None = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Create a paid Checkout session. No trial_period_days (no auto-convert)."""
    import stripe

    key = stripe_secret_key()
    if not key:
        raise BillingError("STRIPE_SECRET_KEY not set")
    stripe.api_key = key
    t = normalize_tier(tier)
    if t not in PAID_INTERNAL_TIERS:
        raise BillingError("Checkout is only for report, briefing, or agent")
    price = price_id_for_tier(t)
    base = _site_base()
    success = success_url or f"{base}/pricing?checkout=success&tier={t}"
    cancel = cancel_url or f"{base}/pricing?checkout=cancel&tier={t}"
    meta = {"product_line": PRODUCT_LINE, "tier": t}
    if user_id:
        meta["user_id"] = user_id
        meta["supabase_user_id"] = user_id
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": success,
        "cancel_url": cancel,
        "metadata": meta,
        "subscription_data": {"metadata": dict(meta)},
        "allow_promotion_codes": True,
    }
    if customer_id:
        params["customer"] = customer_id
    elif customer_email:
        params["customer_email"] = customer_email
    session = stripe.checkout.Session.create(**params)
    return {"id": session.id, "url": session.url, "tier": t}


def create_portal_session(*, customer_id: str, return_url: str | None = None) -> dict[str, Any]:
    import stripe

    key = stripe_secret_key()
    if not key:
        raise BillingError("STRIPE_SECRET_KEY not set")
    if not customer_id:
        raise BillingError("No Stripe customer on this account")
    stripe.api_key = key
    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url or f"{_site_base()}/pricing",
    )
    return {"url": portal.url}


def _price_from_obj(obj: dict) -> str:
    items = ((obj.get("items") or {}).get("data")) or []
    if items:
        return str((items[0].get("price") or {}).get("id") or "")
    display = obj.get("display_items") or []
    if display:
        return str((display[0].get("price") or {}).get("id") or "")
    lines = ((obj.get("lines") or {}).get("data")) or []
    if lines:
        return str((lines[0].get("price") or {}).get("id") or "")
    return str((obj.get("price") or {}).get("id") or "")


def resolve_event_tier(obj: dict) -> str | None:
    meta = obj.get("metadata") or {}
    tier = tier_from_metadata(meta)
    if tier:
        return tier
    return tier_from_price_id(_price_from_obj(obj))


def map_stripe_event(event: dict) -> dict[str, Any] | None:
    """Map a verified Stripe event to an apply_subscription payload, or None to skip."""
    etype = str(event.get("type") or "")
    obj = (event.get("data") or {}).get("object") or {}
    meta = obj.get("metadata") or {}
    if not is_cassandra_event(meta):
        return {"action": "skip", "reason": "not_cassandra"}

    if etype in (
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "invoice.paid",
    ):
        tier = resolve_event_tier(obj)
        email = (
            obj.get("customer_email")
            or obj.get("customer_details", {}).get("email")
            or meta.get("email")
        )
        user_id = meta.get("user_id") or meta.get("supabase_user_id")
        status = "active"
        raw_status = str(obj.get("status") or "").lower()
        if etype == "customer.subscription.updated" and raw_status in (
            "canceled",
            "unpaid",
            "past_due",
        ):
            status = raw_status
        elif raw_status == "trialing":
            # We do not sell a Stripe trial. Treat as active paid if it appears.
            status = "active"
        external_id = str(
            obj.get("subscription")
            or obj.get("id")
            or ""
        )
        return {
            "action": "upsert",
            "etype": etype,
            "tier": tier,
            "email": email,
            "user_id": user_id,
            "status": status,
            "external_id": external_id,
            "customer_id": obj.get("customer"),
        }

    if etype == "customer.subscription.deleted":
        user_id = meta.get("user_id") or meta.get("supabase_user_id")
        return {
            "action": "cancel",
            "etype": etype,
            "tier": str(meta.get("tier") or "report"),
            "email": meta.get("email"),
            "user_id": user_id,
            "status": "canceled",
            "external_id": str(obj.get("id") or ""),
            "customer_id": obj.get("customer"),
        }

    return {"action": "ignore", "etype": etype}


def apply_mapped_event(mapped: dict[str, Any]) -> dict[str, Any]:
    """Persist a mapped event via supabase_auth.apply_subscription when possible."""
    from src.db.supabase_auth import apply_subscription, find_user_id_by_email

    action = mapped.get("action")
    if action in (None, "skip", "ignore"):
        return {"applied": False, **mapped}
    if action == "upsert" and not mapped.get("tier"):
        return {"applied": False, "reason": "no_tier", **mapped}

    user_id = mapped.get("user_id")
    email = mapped.get("email")
    if not user_id and email:
        user_id = find_user_id_by_email(str(email))
    if not user_id:
        return {"applied": False, "reason": "no_user", **mapped}

    apply_subscription(
        user_id=str(user_id),
        tier=str(mapped.get("tier") or "report"),
        provider="stripe",
        external_id=str(mapped.get("external_id") or ""),
        status=str(mapped.get("status") or "active"),
        stripe_customer_id=str(mapped.get("customer_id") or "") or None,
    )
    return {"applied": True, "user_id": user_id, **mapped}
