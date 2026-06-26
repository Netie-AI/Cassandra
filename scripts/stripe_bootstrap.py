#!/usr/bin/env python3
"""Create Cassandra Stripe products/prices/payment links (test mode)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TIERS = [
    ("report", "Cassandra Report", 499, "report"),
    ("pro", "Cassandra Pro", 999, "briefing"),
    ("api", "Cassandra API", 4999, "agent"),
]


def main() -> int:
    from src.tools._env import load_env

    load_env()
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        print("STRIPE_SECRET_KEY not set in .env")
        return 1
    try:
        import stripe
    except ImportError:
        print("pip install stripe")
        return 1

    stripe.api_key = key
    urls: dict[str, str] = {}
    price_ids: dict[str, str] = {}

    for tier_key, name, cents, internal_tier in TIERS:
        product = stripe.Product.create(
            name=name,
            metadata={"product_line": "cassandra", "tier": tier_key},
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=cents,
            currency="usd",
            recurring={"interval": "month"},
            metadata={"product_line": "cassandra", "tier": tier_key},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={"product_line": "cassandra", "tier": tier_key, "internal_tier": internal_tier},
            subscription_data={"trial_period_days": 7, "metadata": {"product_line": "cassandra", "tier": tier_key}},
        )
        urls[tier_key] = link.url
        price_ids[tier_key] = price.id
        print(f"{name}: {link.url}")

    print("\nPaste into .env:")
    print(f"STRIPE_PRICE_REPORT={price_ids.get('report', '')}")
    print(f"STRIPE_PRICE_PRO={price_ids.get('pro', '')}")
    print(f"STRIPE_PRICE_API={price_ids.get('api', '')}")

    config_path = ROOT / "web" / "static" / "config.js"
    print("\nconfig.js snippet:")
    print(json.dumps({"stripe_report_url": urls.get("report"), "stripe_pro_url": urls.get("pro"), "stripe_api_url": urls.get("api")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
