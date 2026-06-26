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


def render_edition_html(
    *,
    crs: float | None,
    phase: str | None,
    phase_conf: float | None,
    asof: str,
    unsub_token: str,
    lang: str = "en",
) -> str:
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
    return tpl.format(
        date=asof,
        crs=crs_val,
        crs_color=color,
        phase=phase_label,
        phase_conf=conf_pct,
        body_excerpt=body_excerpt(asof, lang),
        share_whatsapp=f"https://wa.me/?text={share_text}",
        share_x=share_x,
        unsub_token=unsub_token,
    )


def render_edition_text(*, crs: float | None, phase: str | None, asof: str) -> str:
    phase_label = (phase or "undetermined").replace("_", " ").title()
    crs_val = f"{crs:.0f}" if crs is not None else "n/a"
    return (
        f"Cassandra desk · {asof}\n"
        f"CRS: {crs_val} · Phase: {phase_label}\n"
        f"Read the full edition: https://crash.netie.ai/newspaper-report\n"
    )
