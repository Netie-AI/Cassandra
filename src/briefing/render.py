"""briefing/render.py: edition dict -> email HTML + plain text. All feed text is escaped (untrusted).

Two channels, each readable on its own: AI (a few AI stories) and Markets (prices, a few market
stories, what is scheduled next). `channel="ai"` or `"markets"` renders one channel only, for
posting to separate groups; `"all"` is the full daily briefing.
"""
from __future__ import annotations

import datetime as dt
import secrets
from html import escape as e
from typing import Any

# Random per process: feed or model text cannot contain it, so a hostile link can never
# receive a subscriber's unsubscribe token when dispatch swaps the placeholder.
UNSUB_PLACEHOLDER = f"__UNSUB_{secrets.token_hex(12)}__"
_SITE = "https://crash.netie.ai"
CHANNEL_NAMES = {"ai": "AI Channel", "markets": "Markets Channel"}
_BAND = ("margin:34px 0 4px;padding:10px 14px;background:#1a1a1a;color:#ffffff;font-size:14px;"
         "font-weight:700;letter-spacing:.12em;text-transform:uppercase;")
_H2 = ("font-family:Georgia,serif;font-size:19px;margin:26px 0 10px;padding-top:12px;"
       "border-top:1px solid #1a1a1a;color:#1a1a1a;")
_SMALL = "font-size:13px;color:#555;"
_LINK = "display:inline-block;padding:12px 0;"          # 44px tap target with the 20px line
_KICKER = "font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#555;"
DISCLAIMER = ("Compiled from public sources by an automated editor and checked by software against each "
              "linked source. An independent publication: not an official communication of any company, "
              "and not investment advice. Please read the source before relying on a report.")


def channel_stories(ed: dict[str, Any], channel: str) -> list[dict]:
    return [s for s in ed["stories"] if s.get("channel", "ai") == channel]


def read_minutes(ed: dict[str, Any], channel: str = "all") -> int:
    stories = ed["stories"] if channel == "all" else channel_stories(ed, channel)
    words = sum(len(str(s.get(k) or "").split()) for s in stories for k in ("headline", "what", "why"))
    words += sum(len(str(ed.get(k) or "").split()) for k in ("hook", "big_picture", "market_take", "outlook"))
    if channel != "ai":
        words += 12 * sum(len(b["rows"]) for b in ed["markets"]) + 25 * (len(ed["events"]) + len(ed.get("calendar", [])))
    return max(1, round(words / 200))


def _day(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%a %d %b")


def _when(ev: dict) -> str:
    span = _day(ev["start"]) if ev["start"] == ev["end"] else f"{_day(ev['start'])} to {_day(ev['end'])}"
    if ev["ongoing"]:
        tag = "under way"
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
    asof = ("Prices at the time of writing" if block["live"] else f"Closing prices, {_day(block['asof'])}")
    if block.get("stale"):
        asof += ". Markets have been closed since then"
    return (
        f"<div style='margin:0 0 18px;'><div style='font-weight:700;'>{e(block['title'])}</div>"
        f"<div style='margin:2px 0 6px;'>{e(block['summary'])}</div>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;font-size:15px;'>{rows}</table>"
        f"<div style='{_SMALL}margin-top:4px;'>{e(asof)}</div></div>"
    )


def _story_html(s: dict, lead: bool = False) -> str:
    kick = " · ".join(x for x in (s.get("tag"), "Singapore" if s.get("region") == "sg" else "") if x)
    kicker = f"<div style='{_KICKER}'>{e(kick)}</div>" if kick else ""
    what = f"<p style='margin:6px 0 0;'>{e(s['what'])}</p>" if s.get("what") else ""
    why = (f"<p style='margin:6px 0 0;'><strong>Why it matters:</strong> {e(s['why'])}</p>" if s.get("why") else "")
    credit = f"As reported by {e(s['source'])}" if s.get("verbatim") else f"Source: {e(s['source'])}"
    url = e(s["url"], quote=True)
    size = 21 if lead else 18
    return (
        f"<div style='margin:14px 0 0;'>{kicker}"
        f"<a href='{url}' style='display:block;padding:8px 0;font-family:Georgia,serif;font-size:{size}px;"
        f"font-weight:700;color:#1a1a1a;text-decoration:none;line-height:1.3;'>{e(s['headline'])}</a>"
        f"{what}{why}"
        f"<a href='{url}' style='{_SMALL}{_LINK}'>{credit}</a></div>"
    )


def _ai_channel(ed: dict[str, Any]) -> list[str]:
    stories = channel_stories(ed, "ai")
    if not stories:
        return []
    parts = [f"<div style='{_BAND}'>{CHANNEL_NAMES['ai']}</div>"]
    parts += [_story_html(s, lead=i == 0) for i, s in enumerate(stories)]
    if ed.get("big_picture"):
        parts.append(f"<h2 style='{_H2}'>The wider trend</h2><p style='margin:0;'>{e(ed['big_picture'])}</p>")
    return parts


def _markets_channel(ed: dict[str, Any]) -> list[str]:
    stories = channel_stories(ed, "markets")
    if not (ed["markets"] or stories or ed["events"] or ed.get("calendar")):
        return []
    parts = [f"<div style='{_BAND}'>{CHANNEL_NAMES['markets']}</div>"]
    if ed["markets"]:
        parts.append(f"<h2 style='{_H2}border-top:0;margin-top:12px;'>Market summary</h2>")
        parts += [_market_html(b) for b in ed["markets"]]
        if ed.get("market_take"):
            parts.append(f"<p style='margin:0;'><strong>In brief:</strong> {e(ed['market_take'])}</p>")
    if stories:
        parts.append(f"<h2 style='{_H2}'>Market news</h2>")
        parts += [_story_html(s) for s in stories]
    if ed.get("outlook") or ed["events"] or ed.get("calendar"):
        parts.append(f"<h2 style='{_H2}'>Looking ahead</h2>")
        if ed.get("outlook"):
            parts.append(f"<p style='margin:0 0 14px;'>{e(ed['outlook'])} "
                         f"<span style='{_SMALL}'>(editorial view, not a forecast)</span></p>")
        for c in ed.get("calendar", []):
            parts.append(
                "<div style='margin:0 0 12px;'>"
                f"<strong>{e(c['title'])}</strong><div style='{_SMALL}'>{e(c['when'])}</div>"
                f"<div>{e(c['plain'][:1].upper() + c['plain'][1:])}.</div></div>"
            )
        for ev in ed["events"]:
            parts.append(
                "<div style='margin:0 0 14px;padding-left:12px;border-left:3px solid #1a1a1a;'>"
                f"<a href='{e(ev['source'], quote=True)}' style='display:block;padding:10px 0;font-weight:700;"
                f"color:#1a1a1a;'>{e(ev['name'])}</a>"
                f"<div style='{_SMALL}'>{e(_when(ev))} · {e(ev.get('where', ''))}</div>"
                f"<div>{e(ev['why'])}</div></div>"
            )
    return parts


def render_html(ed: dict[str, Any], channel: str = "all") -> str:
    name = "AI &amp; Markets Briefing" if channel == "all" else f"{CHANNEL_NAMES[channel]}"
    stories = ed["stories"] if channel == "all" else channel_stories(ed, channel)
    preheader = ed.get("hook") or (stories[0]["headline"] if stories else "")
    parts = [
        f"<div style='display:none;max-height:0;overflow:hidden;'>{e(preheader)}</div>",
        "<div style=\"max-width:600px;margin:0 auto;padding:0 16px;font-family:'DM Sans',Arial,sans-serif;"
        "font-size:16px;line-height:1.6;color:#1a1a1a;\">",
        "<div style='padding:16px 0 4px;'>"
        "<div style='font-family:Georgia,serif;font-size:24px;font-weight:700;line-height:1.2;'>Cassandra</div>"
        f"<div style='font-size:13px;color:#555;'>{name} · {e(ed['title'])} · "
        f"{e(ed['date_label']).replace(' ', '&nbsp;')} · {read_minutes(ed, channel)}&nbsp;min&nbsp;read</div></div>",
    ]
    if ed.get("hook") and channel == "all":
        parts.append(f"<p style='font-size:17px;line-height:1.5;margin:14px 0 0;padding:12px 14px;"
                     f"background:#f3f1ed;'><strong>Summary.</strong> {e(ed['hook'])}</p>")
    if channel in ("all", "ai"):
        parts += _ai_channel(ed)
    if channel in ("all", "markets"):
        parts += _markets_channel(ed)

    if ed["glossary"]:
        parts.append(f"<h2 style='{_H2}margin-top:34px;'>Glossary</h2>")
        parts += [f"<p style='margin:0 0 8px;'><strong>{e(g['term'])}:</strong> {e(g['plain'])}</p>"
                  for g in ed["glossary"]]

    notes = "".join(f"<br>Note: {e(p)}." for p in ed["problems"])
    prices = "Prices from Yahoo Finance. " if channel != "ai" else ""
    parts.append(
        f"<div style='font-size:13px;color:#666;border-top:1px solid #e5e5e5;margin-top:28px;padding:12px 0;'>"
        f"{prices}{DISCLAIMER}{notes}<br>"
        f"<a href='{_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}' "
        f"style='color:#666;{_LINK}'>Unsubscribe</a>"
        "</div></div>"
    )
    return "\n".join(parts)


def render_page(ed: dict[str, Any], channel: str = "all") -> str:
    """Standalone preview page (browser), same body as the email."""
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{e(ed['subject'])}</title></head><body style='margin:0;background:#fff;'>"
            f"{render_html(ed, channel)}</body></html>")


def _story_text(s: dict) -> list[str]:
    lines = [s["headline"]]
    if s.get("what"):
        lines.append(s["what"])
    if s.get("why"):
        lines.append(f"Why it matters: {s['why']}")
    return lines + [f"{'As reported by' if s.get('verbatim') else 'Source:'} {s['source']}: {s['url']}", ""]


def render_text(ed: dict[str, Any], channel: str = "all") -> str:
    name = "AI & MARKETS BRIEFING" if channel == "all" else CHANNEL_NAMES[channel].upper()
    lines = [f"CASSANDRA {name} · {ed['title']} · {ed['date_label']}", ""]
    if ed.get("hook") and channel == "all":
        lines += [f"Summary. {ed['hook']}", ""]
    if channel in ("all", "ai") and channel_stories(ed, "ai"):
        lines += ["== AI CHANNEL ==", ""]
        for s in channel_stories(ed, "ai"):
            lines += _story_text(s)
        if ed.get("big_picture"):
            lines += [f"The wider trend: {ed['big_picture']}", ""]
    if channel in ("all", "markets"):
        lines += ["== MARKETS CHANNEL ==", ""]
        for b in ed["markets"]:
            lines.append(f"{b['title'].upper()} (as of {b['asof']}): {b['summary']}")
            lines += [f"  {r['label']}: {r['pct_text']} ({r['close']})" for r in b["rows"]]
            lines.append("")
        if ed.get("market_take"):
            lines += [f"In brief: {ed['market_take']}", ""]
        for s in channel_stories(ed, "markets"):
            lines += _story_text(s)
        if ed.get("outlook"):
            lines += [f"Looking ahead (editorial view): {ed['outlook']}", ""]
        for c in ed.get("calendar", []):
            lines += [f"{c['title']}, {c['when']}: {c['plain']}.", ""]
        for ev in ed["events"]:
            lines += [f"{ev['name']}, {_when(ev)}: {ev['why']}", ""]
    for g in ed["glossary"]:
        lines.append(f"{g['term']}: {g['plain']}")
    lines += [""] + [f"Note: {p}." for p in ed["problems"]]
    lines += [DISCLAIMER, f"Unsubscribe: {_SITE}/api/digest/unsubscribe?token={UNSUB_PLACEHOLDER}"]
    return "\n".join(lines)
