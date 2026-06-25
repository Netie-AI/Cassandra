"""Client + server diagnostic bundle for contact/support emails."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from typing import Any

APP_VERSION = "0.9.0-deploy"


def server_snapshot() -> dict[str, Any]:
    from src.store import latest_score

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
    return {
        "app_version": APP_VERSION,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "latest_score": compact,
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
