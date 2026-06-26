"""Newsletter send — Resend batch dispatch + single-edition helper."""
from __future__ import annotations

import argparse
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Iterator

import httpx

from .render import render_edition_html, render_edition_text

_BATCH_SIZE = 100


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") or os.getenv("SMTP_HOST"))


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def send_edition(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    tags: dict[str, str] | None = None,
    purpose: str = "digest",
) -> dict[str, Any]:
    """Send one edition email. Raises RuntimeError if no provider configured."""
    if os.getenv("RESEND_API_KEY"):
        return _send_resend(to=to, subject=subject, html=html, text=text, tags=tags, purpose=purpose)
    if os.getenv("SMTP_HOST"):
        return _send_smtp(to=to, subject=subject, html=html, text=text)
    raise RuntimeError("No email provider configured — set RESEND_API_KEY or SMTP_* in .env")


def dispatch_digest(*, dry_run: bool = False) -> dict[str, Any]:
    """
    Batch-send the latest edition to confirmed digest subscribers.
    Uses Resend /emails/batch (100 per call) when RESEND_API_KEY is set.
    """
    from src.store import latest_score, list_digest_recipients, log_newsletter_send, mark_digest_sent

    recipients = list_digest_recipients()
    score = latest_score() or {}
    crs = score.get("crs")
    band = score.get("band") or "n/a"
    asof = score.get("asof") or "unknown"
    phase = score.get("phase")
    phase_conf = score.get("phase_confidence")
    subject = (
        f"Cassandra daily - CRS {crs:.0f} ({band}) - {asof}"
        if crs is not None
        else f"Cassandra daily - {asof}"
    )

    if dry_run:
        return {
            "sent": 0,
            "failed": 0,
            "dry_run": True,
            "recipients": [r["email"] for r in recipients],
            "subject": subject,
        }

    if not recipients:
        return {"sent": 0, "failed": 0, "dry_run": False, "subject": subject}

    if not is_configured():
        raise RuntimeError("No email provider configured — set RESEND_API_KEY or SMTP_* in .env")

    if os.getenv("RESEND_API_KEY"):
        return _dispatch_resend_batch(recipients, subject, crs, phase, phase_conf, asof)

    return _dispatch_sequential(recipients, subject, crs, phase, phase_conf, asof)


def _dispatch_resend_batch(
    recipients: list[dict],
    subject: str,
    crs: float | None,
    phase: str | None,
    phase_conf: float | None,
    asof: str | int,
) -> dict[str, Any]:
    from src.store import log_newsletter_send, mark_digest_sent

    key = os.environ["RESEND_API_KEY"]
    from_addr = _from_address("digest")
    reply_to = os.getenv("RESEND_REPLY_TO")
    sent = 0
    failed = 0
    sent_emails: list[str] = []

    for chunk in _chunks(recipients, _BATCH_SIZE):
        batch: list[dict[str, Any]] = []
        chunk_emails: list[str] = []
        for rec in chunk:
            email = rec["email"]
            html = render_edition_html(
                crs=crs,
                phase=phase,
                phase_conf=phase_conf,
                asof=str(asof),
                unsub_token=rec["unsub_token"],
            )
            text = render_edition_text(crs=crs, phase=phase, asof=str(asof))
            item: dict[str, Any] = {
                "from": from_addr,
                "to": [email],
                "subject": subject,
                "html": html,
                "text": text,
            }
            if reply_to:
                item["reply_to"] = reply_to
            batch.append(item)
            chunk_emails.append(email)

        try:
            r = httpx.post(
                "https://api.resend.com/emails/batch",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=batch,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json().get("data") or []
            chunk_sent = sum(1 for row in data if isinstance(row, dict) and row.get("id"))
            sent += chunk_sent
            failed += len(chunk) - chunk_sent
            for email in chunk_emails[:chunk_sent]:
                log_newsletter_send(email, subject, ok=True)
                sent_emails.append(email)
            for email in chunk_emails[chunk_sent:]:
                log_newsletter_send(email, subject, ok=False, detail="batch item failed")
        except Exception as exc:
            failed += len(chunk)
            for email in chunk_emails:
                log_newsletter_send(email, subject, ok=False, detail=str(exc)[:200])

    mark_digest_sent(sent_emails)
    return {"sent": sent, "failed": failed, "dry_run": False, "subject": subject, "provider": "resend_batch"}


def _dispatch_sequential(
    recipients: list[dict],
    subject: str,
    crs: float | None,
    phase: str | None,
    phase_conf: float | None,
    asof: str | int,
) -> dict[str, Any]:
    import time

    from src.store import log_newsletter_send, mark_digest_sent

    sent = 0
    failed = 0
    sent_emails: list[str] = []
    for rec in recipients:
        email = rec["email"]
        html = render_edition_html(
            crs=crs,
            phase=phase,
            phase_conf=phase_conf,
            asof=str(asof),
            unsub_token=rec["unsub_token"],
        )
        text = render_edition_text(crs=crs, phase=phase, asof=str(asof))
        try:
            send_edition(to=email, subject=subject, html=html, text=text, tags={"type": "digest", "asof": str(asof)})
            log_newsletter_send(email, subject, ok=True)
            sent_emails.append(email)
            sent += 1
        except Exception as exc:
            log_newsletter_send(email, subject, ok=False, detail=str(exc)[:200])
            failed += 1
        time.sleep(0.1)

    mark_digest_sent(sent_emails)
    return {"sent": sent, "failed": failed, "dry_run": False, "subject": subject, "provider": "smtp_or_single"}


def _from_address(purpose: str = "digest") -> str:
    if purpose in ("auth", "contact"):
        addr = os.getenv("RESEND_FROM_AUTH")
        if addr:
            return addr
    addr = os.getenv("RESEND_FROM_DIGEST") or os.getenv("NEWSLETTER_FROM")
    if addr:
        return addr
    if purpose in ("auth", "contact"):
        return "no-reply@mail.netie.ai"
    return "cassandra@mail.netie.ai"


def _send_resend(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None,
    tags: dict[str, str] | None,
    purpose: str = "digest",
) -> dict[str, Any]:
    key = os.environ["RESEND_API_KEY"]
    body: dict[str, Any] = {
        "from": _from_address(purpose),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    reply_to = os.getenv("RESEND_REPLY_TO")
    if reply_to:
        body["reply_to"] = reply_to
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
