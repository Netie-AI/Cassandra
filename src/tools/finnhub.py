"""
src/tools/finnhub.py — Finnhub: company news + market sentiment (FALLBACK for Alpha Vantage)

Role in routing: FALLBACK news source. Use if Alpha Vantage is rate-limited or unavailable.
Key: FINNHUB_API_KEY (free tier: 60 calls/min).

Returns NewsItems and a MetricReading for av_news_sentiment (same name as alphavantage.py
so the orchestrator can use either transparently — the schema is the same).

Also provides:
  finnhub_sentiment_score — factor S, from Finnhub's company news sentiment endpoint.

Run standalone: python -m src.tools.finnhub
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading, NewsItem
from ._env import get_key, load_env

load_env()
_BASE = "https://finnhub.io/api/v1"


def _key() -> str:
    k = get_key("FINNHUB_API_KEY")
    if not k:
        raise EnvironmentError("FINNHUB_API_KEY not set")
    return k


def _get(path: str, params: dict | None = None) -> Optional[dict | list]:
    try:
        r = httpx.get(f"{_BASE}{path}", params={"token": _key(), **(params or {})}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _classify_tag(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["fed", "fomc", "rate hike", "powell", "inflation"]):
        return "fed"
    if any(w in t for w in ["capex", "capital expenditure", "data center", "ai spending"]):
        return "capex"
    if any(w in t for w in ["supply", "inventory", "hbm", "dram", "nand", "shortage"]):
        return "supply"
    if any(w in t for w in ["tariff", "antitrust", "china", "export control", "sanction"]):
        return "geo"
    return "other"


def fetch_market_news(category: str = "general", limit: int = 50) -> tuple[list[NewsItem], list[MetricReading]]:
    """Pull general market news and compute a mean bearish-sentiment score."""
    now = dt.datetime.utcnow()
    data = _get("/news", {"category": category, "minId": 0})
    if not data or not isinstance(data, list):
        return [], [MetricReading(name="av_news_sentiment", factor="S", raw_value=None,
                                  direction=Direction.BEARISH_HIGH,
                                  source="Finnhub:news", asof=now, note="pull failed")]

    items: list[NewsItem] = []
    scores: list[float] = []

    for art in data[:limit]:
        headline = art.get("headline", "")
        summary = art.get("summary", "") or art.get("headline", "")
        url = art.get("url", "")
        ts = art.get("datetime", 0)
        pub = dt.datetime.utcfromtimestamp(ts) if ts else now

        # Finnhub doesn't provide a raw score; infer from headline keywords
        neg_words = ["crash", "collapse", "cut", "miss", "layoff", "fear", "fall", "plunge",
                     "recession", "deficit", "decline", "loss", "warning", "risk"]
        pos_words = ["beat", "surge", "record", "rally", "boom", "growth", "profit", "raise"]
        txt = (headline + " " + summary).lower()
        neg = sum(1 for w in neg_words if w in txt)
        pos = sum(1 for w in pos_words if w in txt)
        score = 0.5 + 0.1 * neg - 0.1 * pos   # baseline neutral; skew for keywords
        score = max(0.0, min(1.0, score))
        scores.append(score)

        items.append(NewsItem(
            headline=headline, summary=summary, url=url, published=pub,
            signal_tag=_classify_tag(txt), severity=round(score, 3),
        ))

    mean_score = sum(scores) / len(scores) if scores else None
    mr = MetricReading(name="av_news_sentiment", factor="S", raw_value=mean_score,
                       direction=Direction.BEARISH_HIGH,
                       source=f"Finnhub:news/{category}", asof=now,
                       note=f"mean bearish proxy={mean_score:.3f} over {len(scores)} articles"
                            if mean_score else "no articles")
    return items, [mr]


def fetch_company_news(ticker: str, days_back: int = 7) -> list[NewsItem]:
    """Company-specific news for the basket (for the News Digestor)."""
    now = dt.datetime.utcnow()
    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()
    data = _get(f"/company-news", {"symbol": ticker, "from": start, "to": end})
    if not data or not isinstance(data, list):
        return []
    items = []
    for art in data:
        ts = art.get("datetime", 0)
        pub = dt.datetime.utcfromtimestamp(ts) if ts else now
        txt = (art.get("headline", "") + " " + (art.get("summary", "") or "")).lower()
        neg = sum(1 for w in ["cut", "miss", "layoff", "fall", "decline"] if w in txt)
        score = min(1.0, 0.5 + 0.1 * neg)
        items.append(NewsItem(headline=art.get("headline", ""), summary=art.get("summary", "") or "",
                              url=art.get("url", ""), published=pub,
                              signal_tag=_classify_tag(txt), severity=round(score, 3)))
    return items


if __name__ == "__main__":
    try:
        items, mrs = fetch_market_news(limit=20)
        print(f"Finnhub market news: {len(items)} articles")
        for m in mrs:
            val = f"{m.raw_value:.3f}" if m.raw_value is not None else "MISSING"
            print(f"  {m.name}: {val}  | {m.note}")
        if items:
            print(f"  sample headline: {items[0].headline[:80]}")
    except EnvironmentError as e:
        print(f"  {e} — set FINNHUB_API_KEY in .env")
