"""Render newsletter HTML from template + store data."""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import quote

_TEMPLATE = Path(__file__).resolve().parent / "template.html"


def crs_color(crs: float | None) -> str:
    if crs is None:
        return "#666666"
    if crs > 65:
        return "#d32f2f"
    if crs > 40:
        return "#e65100"
    return "#2e7d32"


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def body_excerpt(asof: str, lang: str = "en", max_paragraphs: int = 3) -> str:
    from src.store import get_newspaper_body

    body = get_newspaper_body(asof, lang) or {}
    raw = body.get("col1_html") or ""
    if not raw:
        return "<p>Today's edition is live on the desk.</p>"
    plain = _strip_html(raw)
    parts = [p.strip() for p in plain.split("\n\n") if p.strip()]
    excerpt = parts[:max_paragraphs]
    return "".join(f"<p style='margin:0 0 12px;'>{escape(p)}</p>" for p in excerpt)


def _tier_body(asof: str, lang: str, depth: str) -> str:
    """Free = short summary. Report = 5-factor. Briefing/Agent = deeper analog + sources."""
    from src.entitlement import normalize_tier

    depth = normalize_tier(depth)
    if depth in ("agent", "vip", "master"):
        depth = "agent"
    if depth == "free":
        return (
            body_excerpt(asof, lang, max_paragraphs=1)
            + "<p style='margin:12px 0 0;color:#666;font-size:13px;'>"
            "Free summary. L + V factors only. S / B / C stay locked after the 90-day Agent trial."
            "</p>"
        )
    if depth == "report":
        return (
            body_excerpt(asof, lang, max_paragraphs=3)
            + "<p style='margin:12px 0 0;font-size:13px;'>"
            "<strong>The Report</strong> — full 5-factor daily, capex NLP, analog comparison."
            "</p>"
        )
    extra = ""
    if depth == "briefing":
        extra = (
            "<p style='margin:12px 0 0;font-size:13px;'><strong>The Briefing</strong> — "
            "10-page depth, AI insights, side-by-side 2000/2008 analog, source attribution.</p>"
        )
    elif depth == "agent":
        extra = (
            "<p style='margin:12px 0 0;font-size:13px;'><strong>The Agent</strong> — "
            "Briefing depth plus watchlist, stock crash scores, JSON API, chat 50/day.</p>"
        )
    return body_excerpt(asof, lang, max_paragraphs=6) + extra


def render_edition_html(
    *,
    crs: float | None,
    phase: str | None,
    phase_conf: float | None,
    asof: str,
    unsub_token: str,
    lang: str = "en",
    tier: str = "free",
) -> str:
    from src.entitlement import newsletter_depth, normalize_tier

    tpl = _TEMPLATE.read_text(encoding="utf-8")
    phase_label = (phase or "undetermined").replace("_", " ").title()
    conf_pct = int(round((phase_conf or 0) * 100)) if phase_conf is not None else 0
    crs_val = f"{crs:.0f}" if crs is not None else "—"
    color = crs_color(crs)
    share_text = quote(f"Cassandra CRS {crs_val} today - {phase_label} https://crash.netie.ai")
    share_x = (
        "https://x.com/intent/tweet?text="
        + quote(f"Cassandra CRS {crs_val} · {phase_label} @netie_ai https://crash.netie.ai")
    )
    depth = newsletter_depth(tier)
    return tpl.format(
        date=asof,
        crs=crs_val,
        crs_color=color,
        phase=phase_label,
        phase_conf=conf_pct,
        body_excerpt=_tier_body(asof, lang, normalize_tier(tier)),
        share_whatsapp=f"https://wa.me/?text={share_text}",
        share_x=share_x,
        unsub_token=unsub_token,
        tier_label=depth,
    )


def render_edition_text(
    *,
    crs: float | None,
    phase: str | None,
    asof: str,
    tier: str = "free",
) -> str:
    from src.entitlement import newsletter_depth, normalize_tier

    phase_label = (phase or "undetermined").replace("_", " ").title()
    crs_val = f"{crs:.0f}" if crs is not None else "n/a"
    depth = newsletter_depth(tier)
    name = normalize_tier(tier)
    return (
        f"Cassandra desk · {asof}\n"
        f"CRS: {crs_val} · Phase: {phase_label}\n"
        f"Edition depth: {depth} (effective_tier={name})\n"
        f"Read the full edition: https://crash.netie.ai/newspaper-report\n"
    )


def preview_tier_bodies(
    *,
    crs: float | None,
    phase: str | None,
    phase_conf: float | None,
    asof: str,
) -> dict[str, dict[str, str]]:
    """Render free / report / briefing / agent bodies for dry-run inspection."""
    out: dict[str, dict[str, str]] = {}
    for tier in ("free", "report", "briefing", "agent"):
        out[tier] = {
            "html": render_edition_html(
                crs=crs,
                phase=phase,
                phase_conf=phase_conf,
                asof=str(asof),
                unsub_token="dry-run",
                tier=tier,
            ),
            "text": render_edition_text(crs=crs, phase=phase, asof=str(asof), tier=tier),
        }
    return out
