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
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

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
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _parse_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        d = parsedate_to_datetime(raw)               # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))   # Atom: ISO 8601
        except ValueError:
            return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)


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
    text = f" {story.title} {story.summary} ".lower()
    return any(k in text for k in keywords)


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:70]


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
    for t, c in zip(res["timestamp"], closes):
        if c is not None:
            by_date[local_date(t)] = float(c)
    # Yahoo often leaves the newest daily bar empty for hours after the close; the meta block
    # has the real last price. Without this the "latest close" is silently a day old.
    if meta.get("regularMarketPrice") is not None and meta.get("regularMarketTime"):
        by_date[local_date(meta["regularMarketTime"])] = float(meta["regularMarketPrice"])
    bars = sorted(by_date.items())
    if len(bars) < 2:
        raise ValueError("fewer than 2 daily bars")
    last_d, last_c = bars[-1]
    prev_c = bars[-2][1]
    week_c = bars[-6][1] if len(bars) >= 6 else None
    now = now or dt.datetime.now(UTC)
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    live = bool(period) and period.get("start", 0) <= now.timestamp() < period.get("end", 0)
    return Quote(
        symbol=symbol, label=label, note=note, close=float(last_c),
        pct_1d=(last_c / prev_c - 1) * 100,
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
