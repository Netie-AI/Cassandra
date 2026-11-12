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
    if v is None:
        return "n/a"
    r = round(v, 1)
    return "flat" if r == 0 else f"{r:+.1f}%"


def _move_word(pct: float | None) -> str:
    """Word chosen from the rounded figure the reader sees, so word and number never disagree."""
    if pct is None:
        return "was unavailable"
    r = round(pct, 1)
    if abs(r) < 0.2:
        return "was flat"
    size = "sharply " if abs(r) >= 1.5 else ("slightly " if abs(r) < 0.5 else "")
    return f"{'rose' if r > 0 else 'fell'} {size}".rstrip()


def _phrase(row: dict) -> str:
    word = _move_word(row["pct"])
    if row["label"].endswith("futures"):          # plural subject
        word = word.replace("was ", "were ")
    return f"{row['label']} {word}" + ("" if row["pct_text"] in ("flat", "n/a") else f" ({row['pct_text']})")


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
    asof = max(r["session_date"] for r in rows)
    for r in rows:                       # a row from an older session (local holiday) says so
        r["old"] = r["session_date"] != asof
    lead = rows[0]
    summary = _phrase(lead)
    # the headline index can hide the real story: name the biggest mover when it is sharp
    movers = [r for r in rows[1:] if r["pct"] is not None and not r["old"]]
    big = max(movers, key=lambda r: abs(r["pct"]), default=None)
    if big and abs(round(big["pct"], 1)) >= 1.5 and abs(big["pct"]) > abs(lead["pct"] or 0):
        summary += f". Biggest move: {_phrase(big)}"
    summary += (" over the past five sessions." if weekly else ".")
    if lead["old"]:
        summary = f"{lead['label']} did not trade in the latest session. " + summary
    stale = bool(today) and not weekly and (today - dt.date.fromisoformat(asof)).days > 3
    return {"title": title, "rows": rows, "summary": summary, "asof": asof,
            "live": any(r["live"] for r in rows), "stale": stale}


def market_dirs(blocks: list[dict]) -> set[str]:
    """Which directions the data actually shows, for checking the model's market commentary."""
    pcts = [round(r["pct"], 1) for b in blocks for r in b["rows"] if r["pct"] is not None]
    return ({"up"} if any(p >= 0.2 for p in pcts) else set()) | ({"down"} if any(p <= -0.2 for p in pcts) else set())


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

    us = market_block("Wall Street" + (", past five sessions" if weekly else " overnight"),
                      sources.fetch_quotes(mk["us"], problems=problems), weekly=weekly, today=today)
    # the morning email only repeats Singapore: the rest of Asia was in last night's edition
    asia_rows = mk["asia"][:1] if edition == "morning" else mk["asia"]
    asia = market_block("Asia" + (", past five sessions" if weekly else " today"),
                        sources.fetch_quotes(asia_rows, problems=problems), weekly=weekly, today=today)
    futures = None
    if edition == "evening":
        futures = market_block("US futures right now", sources.fetch_quotes(mk["futures"], problems=problems),
                               today=today)
    # morning leads with the US close; evening leads with Asia, then the futures hint
    blocks = {"morning": [us, asia], "evening": [asia, futures, us], "weekly": [us, asia]}[edition]
    if edition == "morning" and asia:
        asia["title"] = "Singapore, last close"
    if edition == "evening" and us:
        us["title"] = "Wall Street, last close"
    # "overnight" / "today" are only true when the market actually traded in that session
    if edition == "morning" and us and (today - dt.date.fromisoformat(us["asof"])).days > 1:
        us["title"] = "Wall Street, last close (no US trading overnight)"
    if edition == "evening" and asia and asia["asof"] != today.isoformat():
        asia["title"] = "Asia, last close (no trading today)"
    blocks = [b for b in blocks if b]
    if not blocks:
        problems.append("no market data at all: market section omitted")

    since = now - dt.timedelta(hours=cfg["lookback_hours"][edition])
    stories = sources.fetch_stories(cfg, since=since, now=now, problems=problems)
    events = sources.upcoming_events(today, horizon_days=14 if not weekly else 45)
    all_events = sources.load_config("events").get("events", [])
    calendar = sources.fetch_calendar(
        cfg, now=now, hours=168 if weekly else 30, tz=tz, problems=problems,
        skip={(ev["ticker"], ev["start"].isoformat()) for ev in all_events if ev.get("ticker")})
    copy = writer.write_copy(stories, edition=edition, date_label=local.strftime("%A %d %B %Y"),
                             market_facts=_facts(blocks), market_dirs=market_dirs(blocks), events=events,
                             calendar=calendar, writers=cfg.get("writers"))
    if copy["writer"] == "wire":
        problems.append(f"stories are shown in their original wording ({copy['writer_note']})")
    if not copy["stories"]:
        problems.append("no AI stories found in the time window")

    date_label = local.strftime("%a %d %b %Y")
    if copy["writer"] == "wire":
        subject = "AI and markets: today's headlines"
    else:
        subject = copy.get("subject") or writer._clip(copy["stories"][0]["headline"], writer.SUBJECT_MAX)
    story_text = " ".join(f"{s['headline']} {s['what']} {s['why']} {s['title']}" for s in copy["stories"])
    glossary_text = (story_text + " " + " ".join(b["title"] for b in blocks) + (" futures" if futures else "")
                     + " " + " ".join(c["title"] for c in calendar))
    return {
        "edition": edition,
        "title": TITLES[edition],
        "date": today.isoformat(),
        "date_label": date_label,
        "generated_at": now.isoformat(timespec="seconds"),
        "subject": subject,
        "hook": copy.get("hook", ""),
        "big_picture": copy.get("big_picture", ""),
        "talking_point": copy.get("talking_point", ""),
        "markets": blocks,
        "market_take": copy.get("market_take", ""),
        "stories": copy["stories"],
        "outlook": copy.get("outlook", ""),
        "events": events,
        "calendar": calendar,
        "glossary": sources.glossary_hits(glossary_text),
        "writer": copy["writer"],
        "rejected": copy.get("rejected", []),
        "problems": problems,
        "candidates": len(stories),
    }
