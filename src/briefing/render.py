"""briefing/render.py: edition dict -> email HTML + plain text. All feed text is escaped (untrusted)."""
from __future__ import annotations

import datetime as dt
from html import escape as e
from typing import Any

UNSUB_PLACEHOLDER = "__UNSUB_TOKEN__"
_SITE = "https://crash.netie.ai"
_H2 = ("font-family:Georgia,serif;font-size:19px;margin:32px 0 12px;padding-top:14px;"
       "border-top:2px solid #1a1a1a;color:#1a1a1a;")
_SMALL = "font-size:12px;color:#666;"


def _day(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%a %d %b")


def _when(ev: dict) -> str:
    span = _day(ev["start"]) if ev["start"] == ev["end"] else f"{_day(ev['start'])} to {_day(ev['end'])}"
    if ev["ongoing"]:
        tag = "happening now"
    elif ev["days_away"] == 0:
        tag = "today"
    elif ev["days_away"] == 1:
        tag = "tomorrow"
    else:
        tag = f"in {ev['days_away']} days"
    if not ev.get("confirmed", True):
        tag += ", date not yet confirmed by the organiser"
    return f"{span} ({tag})"


def _market_html(block: dict) -> str:
    rows = ""
    for r in block["rows"]:
        pct = r["pct"]
        color = "#666" if pct is None or abs(pct) < 0.05 else ("#15803D" if pct > 0 else "#B91C1C")
        rows += (
            "<tr>"
            f"<td style='padding:6px 0;border-bottom:1px solid #eee;'><strong>{e(r['label'])}</strong>"
            f"<br><span style='{_SMALL}'>{e(r['note'])}</span></td>"
            f"<td style='padding:6px 0;border-bottom:1px solid #eee;text-align:right;{_SMALL}'>{e(r['close'])}</td>"
            f"<td style='padding:6px 0 6px 12px;border-bottom:1px solid #eee;text-align:right;"
            f"font-weight:700;color:{color};white-space:nowrap;'>{e(r['pct_text'])}</td>"
            "</tr>"
        )
    asof = ("prices still moving, snapshot taken when this email was written" if block["live"]
            else f"closing prices, {_day(block['asof'])}")
    if block.get("stale"):
        asof += ". Markets have been closed since then"
    return (
        f"<div style='margin:0 0 18px;'><div style='font-weight:700;font-size:15px;'>{e(block['title'])}</div>"
        f"<div style='font-size:15px;margin:2px 0 6px;'>{e(block['summary'])}</div>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;font-size:14px;'>{rows}</table>"
        f"<div style='{_SMALL}margin-top:4px;'>{e(asof)}</div></div>"
    )


def _story_html(s: dict) -> str:
    why = (f"<p style='margin:6px 0 0;'><strong>Why it matters:</strong> {e(s['why'])}</p>" if s.get("why") else "")
    what = f"<p style='margin:6px 0 0;'>{e(s['what'])}</p>" if s.get("what") else ""
    flag = " 🇸🇬" if s.get("region") == "sg" else ""
    return (
        "<div style='margin:0 0 22px;'>"
        f"<a href='{e(s['url'], quote=True)}' style='font-family:Georgia,serif;font-size:17px;font-weight:700;"
        f"color:#1a1a1a;text-decoration:none;line-height:1.35;'>{e(s['headline'])}{flag}</a>"
        f"{what}{why}"
        f"<p style='margin:6px 0 0;{_SMALL}'>Source: <a href='{e(s['url'], quote=True)}' "
        f"style='color:#666;'>{e(s['source'])}</a></p></div>"
    )


def render_html(ed: dict[str, Any]) -> str:
    parts = [
        "<div style=\"max-width:600px;margin:0 auto;font-family:'DM Sans',Arial,sans-serif;"
        "font-size:15px;line-height:1.6;color:#1a1a1a;\">",
        "<div style='border-bottom:2px solid #1a1a1a;padding:16px 0;'>"
        "<span style='font-family:Georgia,serif;font-size:22px;font-weight:700;'>Cassandra</span>"
        f"<span style='font-size:11px;color:#666;margin-left:12px;'>AI Briefing · {e(ed['title'])} · "
        f"{e(ed['date_label'])}</span></div>",
    ]
    if ed.get("hook"):
        parts.append(f"<p style='font-size:17px;line-height:1.55;margin:20px 0 0;'>{e(ed['hook'])}</p>")

    if ed["markets"]:
        parts.append(f"<h2 style='{_H2}'>Markets in 30 seconds</h2>")
        parts += [_market_html(b) for b in ed["markets"]]
        if ed.get("market_take"):
            parts.append(f"<p style='margin:0;'><strong>In plain English:</strong> {e(ed['market_take'])}</p>")

    if ed["stories"]:
        label = "This week in AI" if ed["edition"] == "weekly" else "What happened in AI"
        parts.append(f"<h2 style='{_H2}'>{label}</h2>")
        parts += [_story_html(s) for s in ed["stories"]]

    if ed.get("outlook") or ed["events"]:
        parts.append(f"<h2 style='{_H2}'>What to watch next</h2>")
        if ed.get("outlook"):
            parts.append(f"<p style='margin:0 0 14px;'><strong>Our read:</strong> {e(ed['outlook'])} "
                         f"<span style='{_SMALL}'>(opinion, not a forecast)</span></p>")
        for ev in ed["events"]:
            parts.append(
                "<div style='margin:0 0 14px;padding-left:12px;border-left:3px solid #1a1a1a;'>"
                f"<a href='{e(ev['source'], quote=True)}' style='font-weight:700;color:#1a1a1a;'>{e(ev['name'])}</a>"
                f"<div style='{_SMALL}'>{e(_when(ev))} · {e(ev.get('where', ''))}</div>"
                f"<div>{e(ev['why'])}</div></div>"
            )

    if ed["glossary"]:
        parts.append(f"<h2 style='{_H2}'>Jargon buster</h2>")
        parts += [f"<p style='margin:0 0 8px;'><strong>{e(g['term'])}:</strong> {e(g['plain'])}</p>"
                  for g in ed["glossary"]]

    notes = "".join(f"<br>Note: {e(p)}." for p in ed["problems"])
    writer = ("Stories rewritten in plain English by an AI editor; every number is checked against the "
              "linked source." if ed["writer"] != "wire" else "")
    parts.append(
        f"<div style='font-size:11px;color:#999;border-top:1px solid #e5e5e5;margin-top:28px;padding:12px 0;'>"
        f"Prices from Yahoo Finance. {writer} Always open the source link before acting on a story."
        f"{notes}<br>Cassandra is a research tool. Not financial advice. "
        f"<a href='{_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}' style='color:#999;'>Unsubscribe</a>"
        "</div></div>"
    )
    return "\n".join(parts)


def render_text(ed: dict[str, Any]) -> str:
    lines = [f"CASSANDRA AI BRIEFING · {ed['title']} · {ed['date_label']}", ""]
    if ed.get("hook"):
        lines += [ed["hook"], ""]
    for b in ed["markets"]:
        lines.append(f"{b['title'].upper()} (as of {b['asof']}): {b['summary']}")
        lines += [f"  {r['label']}: {r['pct_text']} ({r['close']})" for r in b["rows"]]
        lines.append("")
    if ed.get("market_take"):
        lines += [f"In plain English: {ed['market_take']}", ""]
    for s in ed["stories"]:
        lines += [s["headline"], s.get("what") or ""]
        if s.get("why"):
            lines.append(f"Why it matters: {s['why']}")
        lines += [f"{s['source']}: {s['url']}", ""]
    if ed.get("outlook"):
        lines += [f"Our read (opinion): {ed['outlook']}", ""]
    for ev in ed["events"]:
        lines += [f"{ev['name']}, {_when(ev)}: {ev['why']}", ""]
    for g in ed["glossary"]:
        lines.append(f"{g['term']}: {g['plain']}")
    lines += [""] + [f"Note: {p}." for p in ed["problems"]]
    lines += ["Not financial advice.", f"Unsubscribe: {_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}"]
    return "\n".join(l for l in lines if l is not None)
