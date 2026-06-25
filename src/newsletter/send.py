"""Newsletter send — Resend (preferred) or SMTP. No send until credentials set."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") or os.getenv("SMTP_HOST"))


def send_edition(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Send one edition email. Returns provider response dict.
    Raises RuntimeError if no provider configured.
    """
    if os.getenv("RESEND_API_KEY"):
        return _send_resend(to=to, subject=subject, html=html, text=text, tags=tags)
    if os.getenv("SMTP_HOST"):
        return _send_smtp(to=to, subject=subject, html=html, text=text)
    raise RuntimeError("No email provider configured — set RESEND_API_KEY or SMTP_* in .env")


def _from_address() -> str:
    return os.getenv("NEWSLETTER_FROM", "Cassandra Desk <desk@crash.netie.ai>")


def _send_resend(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None,
    tags: dict[str, str] | None,
) -> dict[str, Any]:
    key = os.environ["RESEND_API_KEY"]
    body: dict[str, Any] = {
        "from": _from_address(),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        body["text"] = text
    if tags:
        body["tags"] = [{"name": k, "value": v} for k, v in tags.items()]
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _send_smtp(*, to: str, subject: str, html: str, text: str | None) -> dict[str, Any]:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_TLS", "true").lower() != "false"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        if user:
            server.login(user, password)
        server.sendmail(_from_address(), [to], msg.as_string())
    return {"ok": True, "provider": "smtp", "to": to}
