"""Newsletter send — Resend batch dispatch + single-edition helper.

Default is --dry-run. Pass --live to actually send. Never required on the
cloud VM: laptop Task Scheduler stubs (0545/0600/1800 MYT) stay on the
laptop; this module documents cron equivalents only.
"""
from __future__ import annotations

import argparse
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Iterator

import httpx

from src.entitlement import effective_tier, newsletter_depth, normalize_tier

from .render import preview_tier_bodies, render_edition_html, render_edition_text

_BATCH_SIZE = 100

# MYT = Asia/Kuala_Lumpur (UTC+8). Laptop xml stubs already exist; cloud uses cron.
CRON_SLOTS_MYT = ("05:45", "06:00", "18:00")
CRON_COMMENT = """
# Cassandra newsletter / desk slots (MYT = UTC+8). Do not require Windows Task Scheduler.
# 05:45 MYT  ->  21:45 UTC previous calendar day
# 06:00 MYT  ->  22:00 UTC previous calendar day
# 18:00 MYT  ->  10:00 UTC same calendar day
#
# 45 21 * * 1-5  cd /opt/cassandra && python -m src.newsletter.send --dry-run
# 0  22 * * 1-5  cd /opt/cassandra && python -m src.newsletter.send --dry-run
# 0  10 * * 1-5  cd /opt/cassandra && python -m src.newsletter.send --dry-run
#
# Live send (ops only, after reviewing dry-run):
#   python -m src.newsletter.send --live
"""


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") or os.getenv("SMTP_HOST"))


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def resolve_recipient_tier(rec: dict) -> str:
    """Digest-only emails stay Free. Registered accounts use entitlement."""
    if rec.get("effective_tier"):
        return normalize_tier(str(rec["effective_tier"]))
    if rec.get("created_at"):
        return effective_tier(
            rec.get("created_at"),
            subscription_tier=rec.get("subscription_tier"),
            subscription_status=rec.get("subscription_status"),
        )
    email = str(rec.get("email") or "")
    try:
        from src.db.supabase_auth import account_for_email

        snap = account_for_email(email)
        return normalize_tier(str(snap.get("effective_tier") or "free"))
    except Exception:
        return "free"


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


def _score_subject(score: dict) -> tuple[str, float | None, str, str | None, float | None, str]:
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
    return subject, crs, band, phase, phase_conf, str(asof)


def dispatch_digest(*, dry_run: bool = True) -> dict[str, Any]:
    """
    Batch-send the latest edition to confirmed digest subscribers.
    dry_run=True (default): print per-tier bodies, send nothing.
    Pass dry_run=False / --live to send.
    """
    from src.store import latest_score, list_digest_recipients

    recipients = list_digest_recipients()
    score = latest_score() or {}
    subject, crs, _band, phase, phase_conf, asof = _score_subject(score)
    previews = preview_tier_bodies(crs=crs, phase=phase, phase_conf=phase_conf, asof=asof)

    resolved: list[dict[str, Any]] = []
    for rec in recipients:
        tier = resolve_recipient_tier(rec)
        resolved.append(
            {
                "email": rec["email"],
                "unsub_token": rec.get("unsub_token"),
                "effective_tier": tier,
                "depth": newsletter_depth(tier),
            }
        )

    if dry_run:
        return {
            "sent": 0,
            "failed": 0,
            "dry_run": True,
            "live": False,
            "recipients": [r["email"] for r in resolved],
            "recipient_tiers": resolved,
            "subject": subject,
            "tier_bodies": {k: v["text"] for k, v in previews.items()},
            "tier_html": {k: v["html"] for k, v in previews.items()},
            "cron_slots_myt": list(CRON_SLOTS_MYT),
        }

    if not recipients:
        return {"sent": 0, "failed": 0, "dry_run": False, "live": True, "subject": subject}

    if not is_configured():
        raise RuntimeError("No email provider configured — set RESEND_API_KEY or SMTP_* in .env")

    if os.getenv("RESEND_API_KEY"):
        return _dispatch_resend_batch(resolved, subject, crs, phase, phase_conf, asof)

    return _dispatch_sequential(resolved, subject, crs, phase, phase_conf, asof)


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
            tier = rec.get("effective_tier") or "free"
            html = render_edition_html(
                crs=crs,
                phase=phase,
                phase_conf=phase_conf,
                asof=str(asof),
                unsub_token=rec["unsub_token"],
                tier=tier,
            )
            text = render_edition_text(crs=crs, phase=phase, asof=str(asof), tier=tier)
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
    return {"sent": sent, "failed": failed, "dry_run": False, "live": True, "subject": subject, "provider": "resend_batch"}


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
        tier = rec.get("effective_tier") or "free"
        html = render_edition_html(
            crs=crs,
            phase=phase,
            phase_conf=phase_conf,
            asof=str(asof),
            unsub_token=rec["unsub_token"],
            tier=tier,
        )
        text = render_edition_text(crs=crs, phase=phase, asof=str(asof), tier=tier)
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
    return {"sent": sent, "failed": failed, "dry_run": False, "live": True, "subject": subject, "provider": "smtp_or_single"}


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
        "text": text,
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


def print_dry_run(out: dict[str, Any]) -> None:
    print("DRY-RUN (no email sent). Pass --live to send.")
    print(f"subject: {out.get('subject')}")
    print(f"cron slots MYT: {', '.join(out.get('cron_slots_myt') or CRON_SLOTS_MYT)}")
    bodies = out.get("tier_bodies") or {}
    for tier in ("free", "report", "briefing", "agent"):
        print(f"\n===== {tier} =====")
        print(bodies.get(tier, "(missing)"))
    resolved = out.get("recipient_tiers") or []
    print(f"\nrecipients: {len(resolved)}")
    for rec in resolved[:20]:
        print(f"  {rec.get('email')}  tier={rec.get('effective_tier')}  depth={rec.get('depth')}")
    if len(resolved) > 20:
        print(f"  ... +{len(resolved) - 20} more")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cassandra newsletter batch dispatch. Dry-run is the default.",
        epilog=CRON_COMMENT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print per-tier bodies and recipients only (default)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually send. Required to leave dry-run. Do not use in CI.",
    )
    args = parser.parse_args()
    dry_run = not args.live
    out = dispatch_digest(dry_run=dry_run)
    if dry_run:
        print_dry_run(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
