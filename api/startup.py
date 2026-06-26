"""Startup activation logging — shows LIVE vs STUB for each integration."""
from __future__ import annotations

import logging
import os

log = logging.getLogger("cassandra.startup")


def log_activation_state() -> None:
    from src.db.supabase_client import is_configured as supabase_live

    checks = {
        "Supabase auth": supabase_live(),
        "OpenRouter LLM": bool(os.getenv("OPENROUTER_API_KEY")),
        "Finnhub movers": bool(os.getenv("FINNHUB_API_KEY")),
        "Resend email": bool(os.getenv("RESEND_API_KEY")),
        "Resend audience": bool(os.getenv("RESEND_AUDIENCE_ID")),
        "Resend digest from": os.getenv("RESEND_FROM_DIGEST", "NOT SET"),
        "Resend auth from": os.getenv("RESEND_FROM_AUTH", "NOT SET"),
        "CF publish": bool(os.getenv("CF_KV_ENDPOINT")),
        "Pipeline key": bool(os.getenv("PIPELINE_KEY")),
    }
    log.info("=== CASSANDRA ACTIVATION STATE ===")
    for svc, active in checks.items():
        if isinstance(active, bool):
            log.info("  %-20s %s", svc, "LIVE" if active else "STUB")
        else:
            log.info("  %-20s %s", svc, active)
    log.info("==================================")
