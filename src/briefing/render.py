"""briefing/render.py: edition dict -> email HTML + plain text. All feed text is escaped (untrusted)."""
from __future__ import annotations

import datetime as dt
import secrets
from html import escape as e
from typing import Any

# Random per process: feed or model text cannot contain it, so a hostile link can never
# receive a subscriber's unsubscribe token when dispatch swaps the placeholder.
UNSUB_PLACEHOLDER = f"__UNSUB_{secrets.token_hex(12)}__"
_SITE = "https://crash.netie.ai"
_H2 = ("font-family:Georgia,serif;font-size:20px;margin:32px 0 12px;padding-top:14px;"
       "border-top:2px solid #1a1a1a;color:#1a1a1a;")
_SMALL = "font-size:13px;color:#555;"
_LINK = "display:inline-block;padding:12px 0;"          # 44px tap target with the 20px line
_KICKER = "font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#555;"


def read_minutes(ed: dict[str, Any]) -> int:
    words = sum(len(str(s.get(k) or "").split()) for s in ed["stories"] for k in ("headline", "what", "why"))
    words += sum(len(str(ed.get(k) or "").split()) for k in ("hook", "big_picture", "market_take", "outlook"))
    words += 12 * sum(len(b["rows"]) for b in ed["markets"]) + 25 * (len(ed["events"]) + len(ed.get("calendar", [])))
    return max(1, round(words / 200))


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


def _row_note(r: dict) -> str:
    note = r["note"]
    if r.get("old"):
        note += f" · last traded {_day(r['session_date'])}"
    if r.get("live"):
        note += " · still trading"
    return note


def _market_html(block: dict) -> str:
    rows = ""
    for r in block["rows"]:
        pct = r["pct"]
        color = "#555" if pct is None or r["pct_text"] == "flat" else ("#15803D" if pct > 0 else "#B91C1C")
        rows += (
            "<tr>"
            f"<td style='padding:7px 0;border-bottom:1px solid #eee;width:62%;'><strong>{e(r['label'])}</strong>"
            f"<br><span style='{_SMALL}'>{e(_row_note(r))}</span></td>"
            f"<td style='padding:7px 0;border-bottom:1px solid #eee;text-align:right;{_SMALL}'>{e(r['close'])}</td>"
            f"<td style='padding:7px 0 7px 12px;border-bottom:1px solid #eee;text-align:right;"
            f"font-weight:700;color:{color};white-space:nowrap;'>{e(r['pct_text'])}</td>"
            "</tr>"
        )
    asof = ("Snapshot taken when this email was written" if block["live"]
            else f"Closing prices, {_day(block['asof'])}")
    if block.get("stale"):
        asof += ". Markets have been closed since then"
    return (
        f"<div style='margin:0 0 18px;'><div style='font-weight:700;'>{e(block['title'])}</div>"
        f"<div style='margin:2px 0 6px;'>{e(block['summary'])}</div>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;font-size:15px;'>{rows}</table>"
        f"<div style='{_SMALL}margin-top:4px;'>{e(asof)}</div></div>"
    )


def _story_html(s: dict) -> str:
    why = (f"<p style='margin:6px 0 0;'><strong>What it means for you:</strong> {e(s['why'])}</p>"
           if s.get("why") else "")
    what = f"<p style='margin:6px 0 0;'>{e(s['what'])}</p>" if s.get("what") else ""
    kick = " · ".join(x for x in (s.get("tag"), "Singapore" if s.get("region") == "sg" else "") if x)
    kicker = f"<div style='{_KICKER}'>{e(kick)}</div>" if kick else ""
    url = e(s["url"], quote=True)
    return (
        f"<div style='margin:0 0 20px;'>{kicker}"
        f"<a href='{url}' style='display:block;padding:9px 0;font-family:Georgia,serif;font-size:19px;"
        f"font-weight:700;color:#1a1a1a;text-decoration:none;line-height:1.35;'>{e(s['headline'])}</a>"
        f"{what}{why}"
        f"<a href='{url}' style='{_SMALL}{_LINK}'>Read the source: {e(s['source'])}</a></div>"
    )


def render_html(ed: dict[str, Any]) -> str:
    stories = ed["stories"]
    preheader = ed.get("hook") or (stories[0]["headline"] if stories else "")
    parts = [
        f"<div style='display:none;max-height:0;overflow:hidden;'>{e(preheader)}</div>",
        "<div style=\"max-width:600px;margin:0 auto;padding:0 16px;font-family:'DM Sans',Arial,sans-serif;"
        "font-size:16px;line-height:1.6;color:#1a1a1a;\">",
        "<div style='padding:16px 0 4px;'>"
        "<div style='font-family:Georgia,serif;font-size:24px;font-weight:700;line-height:1.2;'>Cassandra</div>"
        f"<div style='font-size:13px;color:#555;'>AI Briefing · {e(ed['title'])} · "
        f"{e(ed['date_label']).replace(' ', '&nbsp;')} · {read_minutes(ed)}&nbsp;min&nbsp;read</div></div>",
    ]
    if ed.get("hook"):
        parts.append(f"<p style='font-size:18px;line-height:1.5;margin:20px 0 0;'>{e(ed['hook'])}</p>")

    if stories:      # the biggest story comes before the numbers
        parts.append(f"<h2 style='{_H2}'>Top story</h2>")
        parts.append(_story_html(stories[0]))
        if ed.get("talking_point"):
            parts.append("<p style='margin:0;padding:12px 14px;background:#f3f1ed;'>"
                         f"<strong>Say this at lunch:</strong> {e(ed['talking_point'])}</p>")

    if ed["markets"]:
        parts.append(f"<h2 style='{_H2}'>Markets in 30 seconds</h2>")
        parts += [_market_html(b) for b in ed["markets"]]
        if ed.get("market_take"):
            parts.append(f"<p style='margin:0;'><strong>In plain English:</strong> {e(ed['market_take'])}</p>")

    if stories[1:]:
        label = "More from the week in AI" if ed["edition"] == "weekly" else "Also in AI"
        parts.append(f"<h2 style='{_H2}'>{label}</h2>")
        parts += [_story_html(s) for s in stories[1:]]

    if ed.get("big_picture"):      # the synthesis reads best once the stories are known
        parts.append(f"<h2 style='{_H2}'>The big picture</h2>"
                     f"<p style='margin:0;font-family:Georgia,serif;font-size:18px;line-height:1.5;'>"
                     f"{e(ed['big_picture'])}</p>")

    if ed.get("outlook") or ed["events"] or ed.get("calendar"):
        parts.append(f"<h2 style='{_H2}'>What to watch next</h2>")
        if ed.get("outlook"):
            parts.append(f"<p style='margin:0 0 14px;'><strong>Our read:</strong> {e(ed['outlook'])} "
                         f"<span style='{_SMALL}'>(opinion, not a forecast)</span></p>")
        for c in ed.get("calendar", []):
            parts.append(
                "<div style='margin:0 0 12px;'>"
                f"<strong>{e(c['title'])}</strong><div style='{_SMALL}'>{e(c['when'])}</div>"
                f"<div>In plain English: {e(c['plain'])}.</div></div>"
            )
        for ev in ed["events"]:
            parts.append(
                "<div style='margin:0 0 14px;padding-left:12px;border-left:3px solid #1a1a1a;'>"
                f"<a href='{e(ev['source'], quote=True)}' style='display:block;padding:10px 0;font-weight:700;"
                f"color:#1a1a1a;'>{e(ev['name'])}</a>"
                f"<div style='{_SMALL}'>{e(_when(ev))} · {e(ev.get('where', ''))}</div>"
                f"<div>{e(ev['why'])}</div></div>"
            )

    if ed["glossary"]:
        parts.append(f"<h2 style='{_H2}'>Jargon buster</h2>")
        parts += [f"<p style='margin:0 0 8px;'><strong>{e(g['term'])}:</strong> {e(g['plain'])}</p>"
                  for g in ed["glossary"]]

    notes = "".join(f"<br>Note: {e(p)}." for p in ed["problems"])
    writer = ("Stories are rewritten in plain English by an AI editor, then checked by software against the "
              "linked source (numbers, direction, quotes). " if ed["writer"] != "wire" else "")
    parts.append(
        "<p style='margin:28px 0 0;'>Know someone who would like this? Forward it to them.</p>"
        f"<div style='font-size:13px;color:#666;border-top:1px solid #e5e5e5;margin-top:16px;padding:12px 0;'>"
        f"Prices from Yahoo Finance. {writer}Open the source link before acting on a story."
        f"{notes}<br>Cassandra is a research tool. Not financial advice.<br>"
        f"<a href='{_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}' "
        f"style='color:#666;{_LINK}'>Unsubscribe</a>"
        "</div></div>"
    )
    return "\n".join(parts)


def render_page(ed: dict[str, Any]) -> str:
    """Standalone preview page (browser), same body as the email."""
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{e(ed['subject'])}</title></head><body style='margin:0;background:#fff;'>"
            f"{render_html(ed)}</body></html>")


def render_text(ed: dict[str, Any]) -> str:
    lines = [f"CASSANDRA AI BRIEFING · {ed['title']} · {ed['date_label']}", ""]
    if ed.get("hook"):
        lines += [ed["hook"], ""]
    for i, s in enumerate(ed["stories"]):
        lines += [s["headline"], s.get("what") or ""]
        if s.get("why"):
            lines.append(f"What it means for you: {s['why']}")
        lines += [f"{s['source']}: {s['url']}", ""]
        if i == 0:
            if ed.get("talking_point"):
                lines += [f"Say this at lunch: {ed['talking_point']}", ""]
            for b in ed["markets"]:
                lines.append(f"{b['title'].upper()} (as of {b['asof']}): {b['summary']}")
                lines += [f"  {r['label']}: {r['pct_text']} ({r['close']})" for r in b["rows"]]
                lines.append("")
            if ed.get("market_take"):
                lines += [f"In plain English: {ed['market_take']}", ""]
    if ed.get("big_picture"):
        lines += [f"The big picture: {ed['big_picture']}", ""]
    if ed.get("outlook"):
        lines += [f"Our read (opinion): {ed['outlook']}", ""]
    for c in ed.get("calendar", []):
        lines += [f"{c['title']}, {c['when']}: {c['plain']}.", ""]
    for ev in ed["events"]:
        lines += [f"{ev['name']}, {_when(ev)}: {ev['why']}", ""]
    for g in ed["glossary"]:
        lines.append(f"{g['term']}: {g['plain']}")
    lines += [""] + [f"Note: {p}." for p in ed["problems"]]
    lines += ["Not financial advice.", f"Unsubscribe: {_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}"]
    return "\n".join(lines)
