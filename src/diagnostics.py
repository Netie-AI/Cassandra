"""Client + server diagnostic bundle for contact/support emails."""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from typing import Any

APP_VERSION = "0.9.0-deploy"

_PHASE_EMOJI = {
    "distribution": "📉",
    "distribution_range": "📉",
    "markdown": "📉",
    "buying_climax": "📉",
    "automatic_reaction": "⚠️",
    "upthrust_utad": "⚠️",
    "undetermined": "⚠️",
    "accumulation": "🔄",
    "secondary_test": "🔄",
    "markup": "📈",
}


def _phase_label(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(raw).replace("_", " ").title()


def _phase_emoji(raw: str | None) -> str:
    if not raw:
        return "⚠️"
    key = str(raw).lower()
    for prefix, emoji in _PHASE_EMOJI.items():
        if key == prefix or key.startswith(prefix):
            return emoji
    return "⚠️"


def phase_snapshot(score: dict | None) -> dict[str, Any]:
    if not score:
        return {"phase_last": None, "phase_conf": None, "phase_emoji": None}
    raw = score.get("phase")
    return {
        "phase_last": _phase_label(raw),
        "phase_conf": score.get("phase_confidence"),
        "phase_emoji": _phase_emoji(raw),
    }


def health_check() -> dict[str, Any]:
    """Minimal health payload for Cloudflare uptime checks."""
    from src.store import latest_score
    from src.tools._env import load_env

    load_env()

    score = latest_score()
    crs = score.get("crs") if score else None
    return {"status": "ok", "version": APP_VERSION, "crs": crs}


def server_snapshot() -> dict[str, Any]:
    from src.db.supabase_client import is_configured as supabase_configured
    from src.store import count_confirmed_digest_subscribers, latest_score
    from src.tools._env import load_env

    load_env()

    score = latest_score()
    compact = None
    if score:
        compact = {
            "asof": score.get("asof"),
            "crs": score.get("crs"),
            "band": score.get("band"),
            "fragility": score.get("fragility"),
            "trigger": score.get("trigger"),
            "phase": score.get("phase"),
            "coverage": score.get("coverage"),
        }
    last_asof = score.get("asof") if score else None
    return {
        "app_version": APP_VERSION,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "latest_score": compact,
        "pipeline_scheduled": bool(os.getenv("PIPELINE_KEY")),
        "finnhub_configured": bool(os.getenv("FINNHUB_API_KEY")),
        "resend_configured": bool(os.getenv("RESEND_API_KEY")),
        "supabase_configured": supabase_configured(),
        "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        "subscriber_count": count_confirmed_digest_subscribers(),
        "last_pipeline_run": f"{last_asof}T00:00:00+00:00" if last_asof else None,
        "coverage_last": score.get("coverage") if score else None,
        "crs_last": score.get("crs") if score else None,
        **phase_snapshot(score),
    }


def format_contact_body(
    *,
    message: str,
    email: str | None,
    client: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return (plain_text, html) for contact email."""
    server = server_snapshot()
    bundle = {"client": client or {}, "server": server}
    plain = (
        f"Contact from Cassandra desk\n\n"
        f"Email: {email or '(not provided)'}\n\n"
        f"Message:\n{message.strip()}\n\n"
        f"--- Diagnostic log ---\n"
        f"{json.dumps(bundle, indent=2, default=str)}\n"
    )
    html = (
        f"<h2>Cassandra contact</h2>"
        f"<p><strong>Email:</strong> {email or '(not provided)'}</p>"
        f"<p><strong>Message:</strong></p><pre>{message.strip()}</pre>"
        f"<p><strong>Diagnostic log:</strong></p>"
        f"<pre>{json.dumps(bundle, indent=2, default=str)}</pre>"
    )
    return plain, html
