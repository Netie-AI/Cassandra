"""Sync digest subscribers with Resend Audiences (list health + compliance)."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("RESEND_AUDIENCE_ID"))


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"}


def _audience_url(suffix: str = "") -> str:
    audience_id = os.environ["RESEND_AUDIENCE_ID"]
    base = f"https://api.resend.com/audiences/{audience_id}/contacts"
    return f"{base}/{suffix}" if suffix else base


def add_contact(email: str, unsub_token: str, *, source: str = "cassandra") -> bool:
    """Add subscriber to Resend audience. No-op when audience not configured."""
    if not is_configured():
        return False
    try:
        r = httpx.post(
            _audience_url(),
            headers=_headers(),
            json={
                "email": email.strip().lower(),
                "unsubscribed": False,
                "first_name": "",
                "last_name": "",
                "data": {"unsub_token": unsub_token, "source": source},
            },
            timeout=30,
        )
        if r.status_code in (200, 201):
            return True
        if r.status_code == 409:
            return update_contact_subscribed(email, unsub_token=unsub_token, source=source)
        log.warning("Resend add_contact %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as exc:
        log.warning("Resend add_contact failed: %s", exc)
        return False


def update_contact_subscribed(
    email: str,
    *,
    unsub_token: str | None = None,
    source: str = "cassandra",
) -> bool:
    contact_id = _find_contact_id(email)
    if not contact_id:
        return add_contact(email, unsub_token or "", source=source)
    payload: dict[str, Any] = {"unsubscribed": False}
    if unsub_token:
        payload["data"] = {"unsub_token": unsub_token, "source": source}
    try:
        r = httpx.patch(
            _audience_url(contact_id),
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        return r.status_code in (200, 201)
    except Exception as exc:
        log.warning("Resend update_contact failed: %s", exc)
        return False


def remove_contact(email: str) -> bool:
    """Remove contact from Resend audience on unsubscribe."""
    if not is_configured():
        return False
    contact_id = _find_contact_id(email)
    if not contact_id:
        return True
    try:
        r = httpx.delete(_audience_url(contact_id), headers=_headers(), timeout=30)
        return r.status_code in (200, 204, 404)
    except Exception as exc:
        log.warning("Resend remove_contact failed: %s", exc)
        return False


def _find_contact_id(email: str) -> str | None:
    email = email.strip().lower()
    try:
        r = httpx.get(_audience_url(), headers=_headers(), timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        rows = data.get("data") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and str(row.get("email", "")).lower() == email:
                cid = row.get("id")
                return str(cid) if cid else None
    except Exception:
        return None
    return None
