"""
briefing/sources.py: keyless inputs for the AI Briefing.

  fetch_stories()  RSS/Atom feeds from config/briefing.yaml  -> list[Story]
  fetch_quotes()   Yahoo chart API (no key)                  -> list[Quote]
  upcoming_events() config/events.yaml                       -> list[dict]
  glossary_hits()  config/glossary.yaml                      -> list[dict]

Every fetch failure is recorded in `problems` (returned to the caller and printed in the
edition footer). Nothing here fails silently.
"""
from __future__ import annotations

import datetime as dt
import html
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
_UA = {"User-Agent": "Mozilla/5.0 (compatible; newsreader/1.0)"}
_ATOM = "{http://www.w3.org/2005/Atom}"
_MAX_FEED_BYTES = 3_000_000
UTC = dt.timezone.utc


def load_config(name: str = "briefing") -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- #
# Stories
# --------------------------------------------------------------------------- #
@dataclass
class Story:
    id: str
    title: str
    summary: str
    url: str
    source: str
    region: str            # "global" | "sg"
    published: dt.datetime  # tz-aware UTC

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d


def _clean(text: str | None, limit: int = 600) -> str:
    # Strip real tags only. A bare "<" or ">" in prose ("cost < $5 ... revenue > $9bn") must
    # survive, otherwise the text between them vanishes and the numbers change meaning.
    text = re.sub(r"</?[a-zA-Z][^<>]*>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _parse_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    raw = re.sub(r"\b(SGT|HKT|MYT)$", "+0800", raw.strip())
    try:
        d = parsedate_to_datetime(raw)               # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))   # Atom: ISO 8601
        except ValueError:
            return None
    if d.tzinfo is None:       # no timezone = we cannot place it in the window honestly
        return None
    return d.astimezone(UTC)


def parse_feed(xml_text: str, *, source: str, region: str = "global") -> list[Story]:
    """Parse RSS 2.0 or Atom. Items without a title, link or date are dropped (undated = unverifiable).
    A story is tagged region "sg" when the feed is Singapore-only or its text mentions Singapore."""
    root = ET.fromstring(xml_text)
    default_region = region
    out: list[tuple] = []
    for it in root.iter("item"):
        src_el = it.find("source")
        out.append((it.findtext("title"), it.findtext("description"), it.findtext("link"),
                    it.findtext("pubDate"), src_el.text if src_el is not None and src_el.text else source))
    for it in root.iter(f"{_ATOM}entry"):
        link = next((l.get("href") for l in it.findall(f"{_ATOM}link")
                     if l.get("rel") in (None, "alternate")), None)
        out.append((it.findtext(f"{_ATOM}title"),
                    it.findtext(f"{_ATOM}summary") or it.findtext(f"{_ATOM}content"),
                    link, it.findtext(f"{_ATOM}published") or it.findtext(f"{_ATOM}updated"), source))
    stories = []
    for title, summary, link, date, src in out:
        pub = _parse_date(date)
        title = _clean(title, 300)
        if not (title and link and pub and link.startswith("http")):
            continue
        # Google News appends " - Publisher" to titles
        if src != source and title.endswith(f" - {src}"):
            title = title[: -len(src) - 3]
        summary = _clean(summary)
        if summary.startswith(title[:60]):       # Google News: description just repeats the title
            summary = ""
        if "singapore" in f"{title} {summary}".lower():
            region = "sg"
        stories.append(Story(id="", title=title, summary=summary, url=link.strip(),
                             source=src, region=region, published=pub))
        region = default_region
    return stories


def _is_ai(story: Story, keywords: list[str]) -> bool:
    """Whole-word match, so "chip" does not fire on Chipotle and "ai" not on Dubai-based."""
    text = f"{story.title} {story.summary}".lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text) for k in keywords)


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch_stories(cfg: dict, *, since: dt.datetime, now: dt.datetime | None = None,
                  problems: list[str] | None = None) -> list[Story]:
    """All AI stories published in (since, now], newest first, de-duplicated by title."""
    now = now or dt.datetime.now(UTC)
    problems = problems if problems is not None else []
    seen: set[str] = set()
    stories: list[Story] = []
    for feed in cfg["feeds"]:
        try:
            r = httpx.get(feed["url"], headers=_UA, timeout=20, follow_redirects=True)
            r.raise_for_status()
            if len(r.content) > _MAX_FEED_BYTES:
                raise ValueError("feed too large")
            items = parse_feed(r.text, source=feed["name"], region=feed.get("region", "global"))
        except Exception as exc:
            problems.append(f"news feed '{feed['name']}' unavailable ({type(exc).__name__})")
            continue
        if not items:
            problems.append(f"news feed '{feed['name']}' returned no readable stories")
        for s in items:
            if not (since < s.published <= now):
                continue
            if not feed.get("ai_only") and not _is_ai(s, cfg["ai_keywords"]):
                continue
            key = _norm_title(s.title)
            if key in seen:
                continue
            seen.add(key)
            stories.append(s)
    stories.sort(key=lambda s: s.published, reverse=True)
    for i, s in enumerate(stories, 1):
        s.id = f"s{i}"
    return stories


# --------------------------------------------------------------------------- #
# Market quotes
# --------------------------------------------------------------------------- #
@dataclass
class Quote:
    symbol: str
    label: str
    note: str
    close: float
    pct_1d: float | None
    pct_5d: float | None
    session_date: str       # exchange-local date of the last bar (YYYY-MM-DD)
    live: bool              # True when the bar is still forming (market open / futures)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_chart(payload: dict, *, symbol: str, label: str, note: str,
                now: dt.datetime | None = None) -> Quote:
    """Turn a Yahoo v8 chart payload (range=1mo, interval=1d) into a Quote. Raises on bad data."""
    res = payload["chart"]["result"][0]
    meta = res["meta"]
    closes = res["indicators"]["quote"][0]["close"]
    off = dt.timedelta(seconds=meta.get("gmtoffset", 0))

    def local_date(ts: float) -> dt.date:
        return (dt.datetime.fromtimestamp(ts, UTC) + off).date()

    by_date: dict[dt.date, float] = {}          # one close per exchange-local session date
    def ok(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0

    for t, c in zip(res["timestamp"], closes):
        if ok(c):
            by_date[local_date(t)] = float(c)
    # Yahoo often leaves the newest daily bar empty for hours after the close; the meta block
    # has the real last price. Without this the "latest close" is silently a day old.
    if ok(meta.get("regularMarketPrice")) and meta.get("regularMarketTime"):
        by_date[local_date(meta["regularMarketTime"])] = float(meta["regularMarketPrice"])
    bars = sorted(by_date.items())
    if len(bars) < 2:
        raise ValueError("fewer than 2 daily bars")
    last_d, last_c = bars[-1]
    prev_c = bars[-2][1]
    week_c = bars[-6][1] if len(bars) >= 6 else None
    now = now or dt.datetime.now(UTC)
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    live = (bool(period) and period.get("start", 0) <= now.timestamp() < period.get("end", 0)
            and last_d == (now + off).date())            # a holiday has trading hours but no trades
    prev_d = bars[-2][0]
    return Quote(
        symbol=symbol, label=label, note=note, close=float(last_c),
        # a gap of more than 4 days means a missing bar: the "one-day" change would span several sessions
        pct_1d=(last_c / prev_c - 1) * 100 if (last_d - prev_d).days <= 4 else None,   # weekend + 1 holiday
        pct_5d=(last_c / week_c - 1) * 100 if week_c else None,
        session_date=last_d.isoformat(),
        live=live,
    )


def fetch_quotes(rows: list[dict], *, problems: list[str] | None = None) -> list[Quote]:
    problems = problems if problems is not None else []
    out: list[Quote] = []
    for row in rows:
        try:
            r = httpx.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{row['symbol']}",
                params={"range": "1mo", "interval": "1d"}, headers=_UA, timeout=20,
            )
            r.raise_for_status()
            out.append(parse_chart(r.json(), symbol=row["symbol"], label=row["label"], note=row.get("note", "")))
        except Exception as exc:
            problems.append(f"price for {row['label']} unavailable ({type(exc).__name__})")
    return out


# --------------------------------------------------------------------------- #
# Calendar: scheduled US data releases + big-tech earnings ("what to expect")
# --------------------------------------------------------------------------- #
def parse_econ(payload: list, *, start: dt.datetime, end: dt.datetime, tz: dt.tzinfo,
               explain: list[dict]) -> list[dict]:
    """US High/Medium-impact releases (and market holidays) in (start, end], with a plain meaning.
    Releases we cannot explain in plain English are left out: this audience would not know them."""
    out, seen = [], set()
    for ev in payload:
        if ev.get("country") != "USD" or ev.get("impact") not in ("High", "Medium", "Holiday"):
            continue
        try:
            when = dt.datetime.fromisoformat(ev["date"])
        except (KeyError, ValueError, TypeError):
            continue
        if when.tzinfo is None or not (start < when <= end):
            continue
        title = str(ev.get("title", "")).strip()
        plain = next((x["plain"] for x in explain
                      if re.search(rf"(?<![a-z]){re.escape(x['match'])}(?![a-z])", title.lower())), None)
        key = (plain, when.date())                    # "CPI m/m" + "Core CPI m/m" are one event to a reader
        if not plain or key in seen:
            continue
        seen.add(key)
        local = when.astimezone(tz)
        stamp = (local.strftime("%a %d %b") if ev["impact"] == "Holiday"          # all-day, the clock time is noise
                 else local.strftime("%a %d %b, %H:%M") + " Singapore time")
        out.append({"kind": "data", "sort": when.astimezone(UTC).isoformat(), "title": title,
                    "when": stamp, "plain": plain})
    return out


_EARN_TIME = {"time-after-hours": "after the US market closes (early next morning in Singapore)",
              "time-pre-market": "before the US market opens (that evening in Singapore)"}


_NY = ZoneInfo("America/New_York")


def parse_earnings(payload: dict, *, day: dt.date, watchlist: dict[str, str],
                   now: dt.datetime | None = None) -> list[dict]:
    """Watchlist companies reporting results on `day` (US date). Results already out by `now`
    are left off: this list is "what to expect", not a recap."""
    out = []
    ny = now.astimezone(_NY) if now else None
    for row in ((payload.get("data") or {}).get("rows") or []):
        name = watchlist.get(str(row.get("symbol", "")).upper())
        if not name:
            continue
        if ny and ny.date() == day:
            released = dt.time(9, 30) if row.get("time") == "time-pre-market" else dt.time(16, 0)
            if ny.time() >= released:
                continue
        timing = _EARN_TIME.get(row.get("time"), "time not announced")
        out.append({"kind": "earnings", "sort": f"{day.isoformat()}T23:00:00", "ticker": row["symbol"].upper(),
                    "title": f"{name} reports quarterly results", "when": f"{day.strftime('%a %d %b')}, {timing}",
                    "plain": "the company's report card for the last three months", "date": day.isoformat()})
    return out


def fetch_calendar(cfg: dict, *, now: dt.datetime, hours: int, tz: dt.tzinfo,
                   skip: set[tuple[str, str]] = frozenset(), problems: list[str] | None = None) -> list[dict]:
    """Scheduled items for the "On the calendar" list. `skip` = (ticker, date) already in events.yaml."""
    problems = problems if problems is not None else []
    cal = cfg.get("calendar") or {}
    items: list[dict] = []
    try:
        r = httpx.get(cal["econ_url"], headers=_UA, timeout=20)
        r.raise_for_status()
        items += parse_econ(r.json(), start=now, end=now + dt.timedelta(hours=hours), tz=tz,
                            explain=cal.get("explain", []))
    except Exception as exc:
        problems.append(f"US economic calendar unavailable ({type(exc).__name__})")
    us_today = now.astimezone(_NY).date()
    failed = 0
    for i in range(int(cal.get("earnings_days_ahead", 5)) + 1):
        day = us_today + dt.timedelta(days=i)
        if day.weekday() >= 5:
            continue
        try:
            r = httpx.get(cal["earnings_url"], params={"date": day.isoformat()}, headers=_UA, timeout=20)
            r.raise_for_status()
            items += [e for e in parse_earnings(r.json(), day=day, watchlist=cal.get("watchlist", {}), now=now)
                      if (e["ticker"], e["date"]) not in skip]
        except Exception:
            failed += 1
    if failed:
        problems.append(f"company results calendar incomplete ({failed} day(s) unavailable)")
    return sorted(items, key=lambda x: x["sort"])


# --------------------------------------------------------------------------- #
# Events + glossary
# --------------------------------------------------------------------------- #
def upcoming_events(today: dt.date, *, horizon_days: int = 45, limit: int = 5,
                    events: list[dict] | None = None) -> list[dict]:
    """Events still running or starting within the horizon. Always includes the next one."""
    events = events if events is not None else load_config("events").get("events", [])
    rows = []
    for ev in events:
        start = ev["start"]
        end = ev.get("end") or start
        if end < today:
            continue
        rows.append({**ev, "start": start.isoformat(), "end": end.isoformat(),
                     "days_away": max((start - today).days, 0), "ongoing": start <= today <= end})
    rows.sort(key=lambda e: e["start"])
    near = [e for e in rows if e["days_away"] <= horizon_days]
    return (near or rows[:1])[:limit]


def glossary_hits(text: str, *, limit: int = 4, terms: list[dict] | None = None) -> list[dict]:
    terms = terms if terms is not None else load_config("glossary").get("terms", [])
    low = text.lower()
    hits = [(low.find(m), t) for t in terms for m in t["match"] if m in low]
    out, seen = [], set()
    for _, t in sorted(hits, key=lambda h: h[0]):
        if t["term"] not in seen:
            seen.add(t["term"])
            out.append({"term": t["term"], "plain": t["plain"]})
    return out[:limit]
