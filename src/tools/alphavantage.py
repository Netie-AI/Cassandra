"""
src/tools/alphavantage.py — Alpha Vantage news+sentiment + OHLCV

APIs used:
  NEWS_SENTIMENT  → feeds News Digestor (NewsItem list + raw sentiment score)
  TIME_SERIES_DAILY_ADJUSTED → feeds Market Structure (OHLCV → breadth / phase)

Free tier: 25 requests/day. Cache aggressively — never hit the same endpoint twice in one cycle.
Paid tier ($50/mo): 75 req/min. Set AV_TIER=paid in env to skip cache TTL enforcement.

MetricReadings produced (factor S — Sentiment, via news_sentiment score):
  av_news_sentiment — mean sentiment score across basket tickers, last N articles (+1 bearish-high)
    direction note: AV scores 0..1 where <0.35 bearish, >0.65 bullish.
    We invert: high bearish-score → high raw_value for BEARISH_HIGH direction.

Run standalone: python -m src.tools.alphavantage
"""
from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading, NewsItem
from ._env import load_env

load_env()
_BASE = "https://www.alphavantage.co/query"
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "store" / "cache" / "av"
_CACHE_TTL_SECONDS = 3600 * 6   # 6h for free tier; reduce for paid


def _key() -> str:
    k = os.environ.get("ALPHAVANTAGE_API_KEY", "")
    if not k:
        raise EnvironmentError("ALPHAVANTAGE_API_KEY not set")
    return k


def _cache_path(fname: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / fname


def _cached_get(params: dict, cache_fname: str) -> Optional[dict]:
    """Return cached JSON if fresh, else None."""
    p = _cache_path(cache_fname)
    if p.exists():
        age = time.time() - p.stat().st_mtime
        if age < _CACHE_TTL_SECONDS:
            import json
            return json.loads(p.read_text())
    return None


def _get(params: dict, cache_fname: str) -> Optional[dict]:
    cached = _cached_get(params, cache_fname)
    if cached is not None:
        return cached
    import json
    params["apikey"] = _key()
    try:
        r = httpx.get(_BASE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        # AV rate-limit response has "Note" key; treat as failure
        if "Note" in data or "Information" in data:
            return None
        _cache_path(cache_fname).write_text(json.dumps(data))
        return data
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# News Sentiment
# --------------------------------------------------------------------------- #
def fetch_news(tickers: list[str], limit: int = 50) -> tuple[list[NewsItem], list[MetricReading]]:
    """
    Pull news+sentiment for the given basket tickers.
    Returns (list[NewsItem], list[MetricReading]) — the MetricReading is the mean sentiment axis.
    """
    ticker_str = ",".join(tickers[:10])     # AV max 10 tickers per call
    cache_name = f"news_{ticker_str[:40]}_{dt.date.today()}.json"
    data = _get({"function": "NEWS_SENTIMENT", "tickers": ticker_str,
                 "limit": limit, "sort": "LATEST"}, cache_name)

    now = dt.datetime.utcnow()
    items: list[NewsItem] = []
    sentiment_scores: list[float] = []

    if not data or "feed" not in data:
        mr = MetricReading(name="av_news_sentiment", factor="S", raw_value=None,
                           direction=Direction.BEARISH_HIGH, source="AlphaVantage:NEWS_SENTIMENT",
                           asof=now, note="pull failed or rate-limited")
        return [], [mr]

    for art in data["feed"]:
        try:
            overall = float(art.get("overall_sentiment_score", 0.0))
            label = art.get("overall_sentiment_label", "Neutral")
            # invert: 1 - bullish_score = bearish pressure
            bearish_proxy = 1.0 - ((overall + 1.0) / 2.0)   # AV scores -1..1, map to 0..1
            sentiment_scores.append(bearish_proxy)
            pub = art.get("time_published", "")
            try:
                pub_dt = dt.datetime.strptime(pub, "%Y%m%dT%H%M%S")
            except ValueError:
                pub_dt = now
            items.append(NewsItem(
                headline=art.get("title", ""),
                summary=art.get("summary", ""),   # already a summary, not full text
                url=art.get("url", ""),
                published=pub_dt,
                signal_tag=_classify_tag(art.get("title", "") + " " + art.get("summary", "")),
                severity=round(bearish_proxy, 3),
                affects_metric=None,
            ))
        except (KeyError, ValueError, TypeError):
            continue

    mean_bearish = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
    mr = MetricReading(
        name="av_news_sentiment", factor="S", raw_value=mean_bearish,
        direction=Direction.BEARISH_HIGH,
        source=f"AlphaVantage:NEWS_SENTIMENT:{ticker_str}",
        asof=now,
        note=f"mean bearish proxy over {len(sentiment_scores)} articles"
    )
    return items, [mr]


def _classify_tag(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["federal reserve", "fed ", "rate hike", "fomc", "powell", "inflation"]):
        return "fed"
    if any(w in t for w in ["capex", "capital expenditure", "data center", "ai spending", "infrastructure"]):
        return "capex"
    if any(w in t for w in ["supply", "inventory", "shortage", "hbm", "dram", "nand", "chip shortage"]):
        return "supply"
    if any(w in t for w in ["antitrust", "tariff", "export control", "china", "sanction"]):
        return "geo"
    return "other"


# --------------------------------------------------------------------------- #
# OHLCV (price data for breadth + phase classifier)
# --------------------------------------------------------------------------- #
def fetch_ohlcv(symbol: str, outputsize: str = "full") -> Optional[list[dict]]:
    """
    Pull daily adjusted OHLCV for a symbol.
    Returns list of {date, open, high, low, close, adj_close, volume} newest-first, or None.
    """
    cache_name = f"ohlcv_{symbol}_{dt.date.today()}.json"
    data = _get({"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol,
                 "outputsize": outputsize}, cache_name)
    if not data or "Time Series (Daily)" not in data:
        return None
    rows = []
    for date_str, v in data["Time Series (Daily)"].items():
        try:
            rows.append({
                "date": dt.date.fromisoformat(date_str),
                "open": float(v["1. open"]),
                "high": float(v["2. high"]),
                "low": float(v["3. low"]),
                "close": float(v["4. close"]),
                "adj_close": float(v["5. adjusted close"]),
                "volume": float(v["6. volume"]),
            })
        except (KeyError, ValueError):
            continue
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def fetch_breadth_proxy(basket: list[str]) -> list[MetricReading]:
    """
    For each symbol in basket, pull the most-recent close and 200dma.
    Return a MetricReading for pct_above_200dma (factor B).
    Note: AV free tier = 25 calls/day; this burns N calls (one per symbol). Use Polygon for production.
    """
    above = 0
    total = 0
    now = dt.datetime.utcnow()
    for sym in basket:
        rows = fetch_ohlcv(sym, outputsize="full")
        if not rows or len(rows) < 200:
            continue
        total += 1
        ma200 = sum(r["adj_close"] for r in rows[:200]) / 200.0
        if rows[0]["adj_close"] > ma200:
            above += 1
        time.sleep(0.5)   # free-tier rate limit

    pct = above / total if total else None
    return [MetricReading(
        name="pct_above_200dma", factor="B", raw_value=pct,
        direction=Direction.BULLISH_HIGH,   # higher pct above 200dma = more bullish = bearish inverted
        source=f"AlphaVantage:TIME_SERIES_DAILY_ADJUSTED:{','.join(basket[:5])}...",
        asof=now, note=f"{above}/{total} above 200dma" if total else "no data"
    )]


if __name__ == "__main__":
    DEMO_BASKET = ["NVDA", "MU", "MSFT"]
    try:
        items, mrs = fetch_news(DEMO_BASKET, limit=10)
        print(f"news: {len(items)} articles")
        for m in mrs:
            print(f"  {m.name}: raw={m.raw_value}  note={m.note}")
        print("ohlcv NVDA:")
        rows = fetch_ohlcv("NVDA", outputsize="compact")
        if rows:
            r = rows[0]
            print(f"  latest={r['date']} close={r['adj_close']:.2f} vol={r['volume']:,.0f}")
        else:
            print("  no data (check ALPHAVANTAGE_API_KEY)")
    except EnvironmentError as e:
        print(f"  {e} — set ALPHAVANTAGE_API_KEY in .env to test live")
