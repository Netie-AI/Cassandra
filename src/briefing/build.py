"""
briefing/build.py: assemble one edition (a plain dict, JSON-serialisable).

Editions (Singapore time):
  morning  07:30 Tue-Sat  what Wall Street did overnight + AI news while you slept + today's watchlist
  evening  20:30 Mon-Fri  how Asia traded today + today's AI news + what to watch in the US tonight
  weekly   09:00 Sun      the week in AI, the week in markets, the week ahead

All market sentences are built here from fetched numbers. The model never writes a number.
"""
from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from . import sources, writer

EDITIONS = ("morning", "evening", "weekly")
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
TITLES = {"morning": "Morning Edition", "evening": "Evening Edition", "weekly": "Weekly Wrap"}


def pick_edition(now_local: dt.datetime, schedule: dict, tolerance_min: int = 90) -> str | None:
    """Which edition is due at `now_local` (within tolerance after its slot), else None."""
    day = _DAYS[now_local.weekday()]
    for name in EDITIONS:
        slot = schedule.get(name) or {}
        if day not in slot.get("days", []):
            continue
        hh, mm = (int(x) for x in slot["time"].split(":"))
        delta = (now_local - now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)).total_seconds()
        if 0 <= delta <= tolerance_min * 60:
            return name
    return None


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{round(v, 1) + 0.0:+.1f}%"   # + 0.0 turns -0.0 into 0.0


def _move_word(pct: float | None) -> str:
    if pct is None:
        return "was unavailable"
    if abs(pct) < 0.15:
        return "was little changed"
    size = "sharply " if abs(pct) >= 1.5 else ("slightly " if abs(pct) < 0.5 else "")
    return f"{'rose' if pct > 0 else 'fell'} {size}".rstrip()


def market_block(title: str, quotes: list[sources.Quote], *, weekly: bool = False,
                 today: dt.date | None = None) -> dict[str, Any] | None:
    """One market table + a deterministic one-line summary. None when no quote arrived."""
    if not quotes:
        return None
    rows = []
    for q in quotes:
        pct = q.pct_5d if weekly else q.pct_1d
        rows.append({"label": q.label, "note": q.note, "close": f"{q.close:,.2f}", "pct": pct,
                     "pct_text": _pct(pct), "session_date": q.session_date, "live": q.live})
    lead = rows[0]
    span = "over the past five sessions" if weekly else ""
    summary = f"{lead['label']} {_move_word(lead['pct'])} ({lead['pct_text']}) {span}".strip() + "."
    dates = sorted({r["session_date"] for r in rows})
    asof = dates[-1]
    stale = bool(today) and not weekly and (today - dt.date.fromisoformat(asof)).days > 3
    return {"title": title, "rows": rows, "summary": summary, "asof": asof,
            "live": any(r["live"] for r in rows), "stale": stale}


def _facts(blocks: list[dict | None]) -> list[str]:
    out = []
    for b in blocks:
        if b:
            out.append(f"{b['title']} (as of {b['asof']}): " +
                       "; ".join(f"{r['label']} {r['pct_text']}" for r in b["rows"]))
    return out


def build_edition(edition: str, *, now: dt.datetime | None = None, cfg: dict | None = None) -> dict[str, Any]:
    if edition not in EDITIONS:
        raise ValueError(f"unknown edition {edition!r}")
    cfg = cfg or sources.load_config()
    tz = ZoneInfo(cfg.get("timezone", "Asia/Singapore"))
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    local = now.astimezone(tz)
    today = local.date()
    problems: list[str] = []
    weekly = edition == "weekly"
    mk = cfg["markets"]

    us = market_block("Wall Street" + (" this week" if weekly else " overnight"),
                      sources.fetch_quotes(mk["us"], problems=problems), weekly=weekly, today=today)
    asia = market_block("Asia" + (" this week" if weekly else " today"),
                        sources.fetch_quotes(mk["asia"], problems=problems), weekly=weekly, today=today)
    futures = None
    if edition == "evening":
        futures = market_block("US futures right now", sources.fetch_quotes(mk["futures"], problems=problems),
                               today=today)
    # morning leads with the US close; evening leads with Asia, then the futures hint
    blocks = {"morning": [us, asia], "evening": [asia, futures, us], "weekly": [us, asia]}[edition]
    if edition == "morning" and asia:
        asia["title"] = "Asia, last close"
    if edition == "evening" and us:
        us["title"] = "Wall Street, last close"
    blocks = [b for b in blocks if b]
    if not blocks:
        problems.append("no market data at all: market section omitted")

    since = now - dt.timedelta(hours=cfg["lookback_hours"][edition])
    stories = sources.fetch_stories(cfg, since=since, now=now, problems=problems)
    events = sources.upcoming_events(today, horizon_days=14 if not weekly else 45)
    copy = writer.write_copy(stories, edition=edition, date_label=local.strftime("%A %d %B %Y"),
                             market_facts=_facts(blocks), events=events)
    if copy["writer"] == "wire":
        problems.append(f"stories are shown in their original wording ({copy['writer_note']})")
    if not copy["stories"]:
        problems.append("no AI stories found in the time window")

    date_label = local.strftime("%a %d %b %Y")
    subject = copy.get("subject") or (copy["stories"][0]["headline"] if copy["stories"] else "AI and markets update")
    story_text = " ".join(f"{s['headline']} {s['what']} {s['why']} {s['title']}" for s in copy["stories"])
    glossary_text = story_text + " " + " ".join(b["title"] for b in blocks) + (" futures" if futures else "")
    return {
        "edition": edition,
        "title": TITLES[edition],
        "date": today.isoformat(),
        "date_label": date_label,
        "generated_at": now.isoformat(timespec="seconds"),
        "subject": f"{subject} | Cassandra {TITLES[edition]}, {local.strftime('%d %b')}",
        "hook": copy.get("hook", ""),
        "markets": blocks,
        "market_take": copy.get("market_take", ""),
        "stories": copy["stories"],
        "outlook": copy.get("outlook", ""),
        "events": events,
        "glossary": sources.glossary_hits(glossary_text),
        "writer": copy["writer"],
        "rejected": copy.get("rejected", []),
        "problems": problems,
        "candidates": len(stories),
    }
