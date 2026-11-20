"""
briefing/build.py: assemble one edition (a plain dict, JSON-serialisable).

Editions (Singapore time):
  morning  07:30 Mon-Fri  Greater China, Singapore and Asia-Pacific first, then Wall Street overnight + AI news
  evening  20:30 Mon-Fri  the US (last close, futures, tonight) first, then how China and Asia traded today + AI news
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


def _move_word(pct: float | None, live: bool = False) -> str:
    """Word chosen from the rounded figure the reader sees, so word and number never disagree.
    Present tense while the market is still trading, past tense once it has closed."""
    if pct is None:
        return "is unavailable" if live else "was unavailable"
    r = round(pct, 1)
    if abs(r) < 0.2:
        return "is flat" if live else "was flat"
    size = "sharply" if abs(r) >= 1.5 else ("slightly" if abs(r) < 0.5 else "")
    if live:
        return f"is {'up' if r > 0 else 'down'} {size}".rstrip()
    return f"{'rose' if r > 0 else 'fell'} {size}".rstrip()


def _phrase(row: dict, live: bool = False) -> str:
    word = _move_word(row["pct"], live)
    if row["label"].endswith("futures"):          # plural subject
        word = word.replace("was ", "were ").replace("is ", "are ")
    return f"{row['label']} {word}" + ("" if row["pct_text"] in ("flat", "n/a") else f" ({row['pct_text']})")


def market_block(title: str, quotes: list[sources.Quote], *, weekly: bool = False,
                 today: dt.date | None = None) -> dict[str, Any] | None:
    """One market table + a deterministic one-line summary. None when no quote arrived."""
    if not quotes:
        return None
    rows = []
    for q in quotes:
        pct = q.pct_5d if weekly else q.pct_1d
        note = q.note
        if q.check == "conflict" and not weekly:
            # two providers disagree about this figure: print neither
            pct, note = None, f"{q.note} · figure withheld, sources disagree"
        rows.append({"label": q.label, "note": note, "close": f"{q.close:,.4f}" if q.fx else f"{q.close:,.2f}",
                     "pct": pct, "pct_text": _pct(pct), "session_date": q.session_date,
                     "live": q.live and not q.fx, "fx": q.fx, "check": q.check, "provider": q.provider})
    # currencies trade around the clock, so they say nothing about which session the table shows
    dated = [r for r in rows if not r["fx"]] or rows
    asof = max(r["session_date"] for r in dated)
    for r in rows:                       # a row from an older session (local holiday) says so
        r["old"] = (not r["fx"]) and r["session_date"] != asof
    lead = rows[0]
    live = any(r["live"] for r in rows)
    summary = _phrase(lead, live)
    # the headline index can hide the real story: name the biggest mover when it is sharp
    movers = [r for r in rows[1:] if r["pct"] is not None and not r["old"] and not r["fx"]]
    big = max(movers, key=lambda r: abs(r["pct"]), default=None)
    if big and abs(round(big["pct"], 1)) >= 1.5 and abs(big["pct"]) > abs(lead["pct"] or 0):
        summary += f". Biggest move: {_phrase(big, live)}"
    summary += (" over the past five sessions." if weekly else ".")
    if lead["old"]:
        summary = f"{lead['label']} did not trade in the latest session. " + summary
    stale = bool(today) and not weekly and (today - dt.date.fromisoformat(asof)).days > 3
    checked = [r for r in rows if r["pct"] is not None]
    return {"title": title, "rows": rows, "summary": summary, "asof": asof,
            "live": live, "stale": stale,
            "confirmed": sum(1 for r in checked if r["check"] == "confirmed"), "checked": len(checked),
            "providers": sorted({r["provider"] for r in rows})}


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


_ASIA = ("china", "singapore", "apac")


def _block_title(edition: str, key: str, name: str, block: dict, today: dt.date) -> str:
    """Title from what the data actually is, not from when the edition was meant to run: a late
    morning run must not call a market that is trading "last close"."""
    asof = dt.date.fromisoformat(block["asof"])
    if edition == "weekly":
        return f"{name}, past five sessions"
    if key == "futures":
        return "US futures before tonight's open" if edition == "evening" else "US futures, latest"
    if block["live"]:
        return f"{name}, trading now"
    if key == "us":
        if edition == "morning":
            return ("Wall Street overnight" if (today - asof).days <= 1
                    else "Wall Street, last close (no US trading overnight)")
        return "Wall Street, last close"
    if asof == today:
        return f"{name} today"
    return f"{name}, last close (no trading today)" if edition == "evening" else f"{name}, last close"


def build_markets(edition: str, cfg: dict, *, today: dt.date, problems: list[str]) -> list[dict]:
    """Market tables for this edition, in the order config/briefing.yaml gives for it."""
    blocks = []
    for key in cfg["editions"][edition]["blocks"]:
        group = cfg["markets"][key]
        block = market_block("", sources.fetch_quotes(group["rows"], problems=problems),
                             weekly=edition == "weekly", today=today)
        if not block:
            continue
        block["key"] = key
        block["title"] = _block_title(edition, key, group["name"], block, today)
        blocks.append(block)
    if not blocks:
        problems.append("no market data at all: market section omitted")
    return blocks


def reader_notes(problems: list[str], n_feeds: int) -> list[str]:
    """What a reader needs to know. A single dead feed among dozens changes nothing they see, so it
    stays in the run log; a missing price, a withheld figure, raw headlines or a large loss of
    sources is always shown."""
    feed = [p for p in problems if p.startswith("news feed ")]
    notes = list(dict.fromkeys(p for p in problems if not p.startswith("news feed ")))
    if n_feeds and len(set(feed)) * 3 >= n_feeds:
        notes.append(f"{len(set(feed))} of {n_feeds} news sources were unavailable, so coverage is thinner than usual")
    return notes


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
    blocks = build_markets(edition, cfg, today=today, problems=problems)
    futures = any(b["key"] == "futures" for b in blocks)

    hours = cfg["lookback_hours"][edition]
    if edition == "morning" and local.weekday() == 0:        # Monday: nothing was sent since Friday evening
        hours = cfg["lookback_hours"].get("after_weekend", hours)
    since = now - dt.timedelta(hours=hours)
    stories = sources.fetch_stories(cfg, since=since, now=now, problems=problems)
    events = sources.upcoming_events(today, horizon_days=14 if not weekly else 45)
    all_events = sources.load_config("events").get("events", [])
    calendar = sources.fetch_calendar(
        cfg, now=now, hours=168 if weekly else 30, tz=tz, problems=problems,
        skip={(ev["ticker"], ev["start"].isoformat()) for ev in all_events if ev.get("ticker")})
    copy = writer.write_copy(stories, edition=edition, date_label=local.strftime("%A %d %B %Y"),
                             market_facts=_facts(blocks), market_dirs=market_dirs(blocks), events=events,
                             calendar=calendar, writers=cfg.get("writers"),
                             sensitive=writer.sensitive_rules(cfg), focus=cfg["editions"][edition].get("focus", ""))
    if copy["writer"] == "wire":
        problems.append(f"stories are shown in their original wording ({copy['writer_note']})")
    if not copy["stories"]:
        problems.append("no stories found in the time window")

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
        "markets": blocks,
        "market_take": copy.get("market_take", ""),
        "stories": copy["stories"],
        "outlook": copy.get("outlook", ""),
        "events": events,
        "calendar": calendar,
        "glossary": sources.glossary_hits(glossary_text),
        "writer": copy["writer"],
        "rejected": copy.get("rejected", []),
        "problems": list(dict.fromkeys(problems)),            # everything, for the run log and the audit
        "notes": reader_notes(problems, len(cfg["feeds"])),   # what is printed to readers
        "candidates": len(stories),
    }
