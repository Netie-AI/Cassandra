"""Newsletter send — Resend batch dispatch + single-edition helper."""
from __future__ import annotations

import argparse
import os
import smtplib
import time
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


def dispatch_digest(*, dry_run: bool = False, rate_per_sec: float = 10.0) -> dict[str, Any]:
    """
    Batch-send the latest edition to confirmed digest subscribers.
    Hard gate: confirmed=1 only. Logs each attempt to contact_log.
    """
    from src.store import latest_score, list_confirmed_digest_subscribers, log_newsletter_send

    recipients = list_confirmed_digest_subscribers()
    score = latest_score() or {}
    crs = score.get("crs")
    band = score.get("band") or "n/a"
    asof = score.get("asof") or "unknown"
    subject = f"Cassandra daily — CRS {crs:.0f} ({band}) · {asof}" if crs is not None else f"Cassandra daily · {asof}"

    if dry_run:
        return {"sent": 0, "failed": 0, "dry_run": True, "recipients": recipients, "subject": subject}

    if not recipients:
        return {"sent": 0, "failed": 0, "dry_run": False, "subject": subject}

    if not is_configured():
        raise RuntimeError("No email provider configured — set RESEND_API_KEY or SMTP_* in .env")

    text = (
        f"Cassandra desk · {asof}\n"
        f"CRS: {crs} · Band: {band}\n"
        f"Read the full edition at https://crash.netie.ai/newspaper-report\n"
    )
    html = (
        f"<p>Cassandra desk · <strong>{asof}</strong></p>"
        f"<p>CRS: <strong>{crs}</strong> · Band: <strong>{band}</strong></p>"
        f'<p><a href="https://crash.netie.ai/newspaper-report">Read today\'s edition</a></p>'
    )

    sent = 0
    failed = 0
    delay = 1.0 / max(rate_per_sec, 1.0)
    for email in recipients:
        try:
            send_edition(to=email, subject=subject, html=html, text=text, tags={"type": "digest", "asof": str(asof)})
            log_newsletter_send(email, subject, ok=True)
            sent += 1
        except Exception as exc:
            log_newsletter_send(email, subject, ok=False, detail=str(exc)[:200])
            failed += 1
        time.sleep(delay)

    return {"sent": sent, "failed": failed, "dry_run": False, "subject": subject}


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
        body["tags"] = [{"name": k, "value": str(v)[:256]} for k, v in tags.items()]
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Cassandra newsletter batch dispatch")
    parser.add_argument("--dry-run", action="store_true", help="Print recipients only")
    args = parser.parse_args()
    out = dispatch_digest(dry_run=args.dry_run)
    recipients = out.get("recipients") or []
    if args.dry_run:
        if not recipients:
            print("0 subscribers (confirmed=1)")
        else:
            for email in recipients[:3]:
                print(email)
            if len(recipients) > 3:
                print(f"... +{len(recipients) - 3} more")
    else:
        print(out)


if __name__ == "__main__":
    main()
