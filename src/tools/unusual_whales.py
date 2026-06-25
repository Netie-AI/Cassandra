"""
src/tools/unusual_whales.py — Unusual Whales API: options flow, dark pool, GEX, retail streak

APIs used (all require UW_API_KEY):
  /api/option-trades/flow-alerts  → live unusual options flow
  /api/darkpool/recent            → dark pool prints
  /api/market/gex                 → market-wide dealer GEX
  /api/market/summary             → retail net-call buying streak

MetricReadings produced (factor S — Sentiment, plus Whale signals):
  uw_net_call_premium  — net call premium (calls - puts); inverted: high = retail call frenzy
  uw_darkpool_short    — dark pool short volume ratio (bearish signal)
  uw_retail_streak     — consecutive weeks net-call-buying by retail (euphoria gauge)
  uw_gex_total         — total signed GEX from UW market summary

UW free tier: limited endpoints. Paid ($48+/mo) unlocks the full flow + dark pool.
Run standalone: python -m src.tools.unusual_whales
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading

_BASE = "https://api.unusualwhales.com"


def _key() -> str:
    k = os.environ.get("UW_API_KEY", "")
    if not k:
        raise EnvironmentError("UW_API_KEY not set")
    return k


def _get(path: str, params: dict | None = None) -> Optional[dict | list]:
    try:
        r = httpx.get(f"{_BASE}{path}",
                      headers={"Authorization": f"Bearer {_key()}",
                               "Content-Type": "application/json"},
                      params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Options flow — net premium direction
# --------------------------------------------------------------------------- #
def fetch_flow_metrics(basket: list[str], lookback_days: int = 5) -> list[MetricReading]:
    """Net call vs put premium across basket, averaged over lookback."""
    now = dt.datetime.utcnow()
    since = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()

    call_premium = put_premium = 0.0
    n = 0
    for ticker in basket[:10]:   # cap to avoid burning rate limit
        data = _get("/api/option-trades/flow-alerts", {"ticker": ticker, "date": since})
        if not data:
            continue
        trades = data if isinstance(data, list) else data.get("data", [])
        for t in trades:
            side = str(t.get("put_call", "")).lower()
            prem = float(t.get("total_premium", 0) or 0)
            if side == "call":
                call_premium += prem
            elif side == "put":
                put_premium += prem
        n += 1

    if n == 0:
        return [MetricReading(name="uw_net_call_premium", factor="S", raw_value=None,
                              direction=Direction.BEARISH_HIGH,
                              source="UnusualWhales:flow-alerts", asof=now,
                              note="no flow data — check UW_API_KEY or paid tier")]

    # high call/put premium ratio = retail euphoria = bearish signal (inverted)
    total = call_premium + put_premium
    call_ratio = call_premium / total if total > 0 else 0.5
    # raw_value: call dominance 0..1; high = bearish (overconfident calls)
    return [MetricReading(name="uw_net_call_premium", factor="S", raw_value=call_ratio,
                          direction=Direction.BEARISH_HIGH,
                          source="UnusualWhales:flow-alerts", asof=now,
                          note=f"call_premium=${call_premium/1e6:.1f}M put=${put_premium/1e6:.1f}M "
                               f"ratio={call_ratio:.2f} over {n} tickers / {lookback_days}d")]


# --------------------------------------------------------------------------- #
# Dark pool
# --------------------------------------------------------------------------- #
def fetch_darkpool_metrics(basket: list[str]) -> list[MetricReading]:
    now = dt.datetime.utcnow()
    short_vol = total_vol = 0.0

    for ticker in basket[:10]:
        data = _get("/api/darkpool/recent", {"ticker": ticker})
        if not data:
            continue
        trades = data if isinstance(data, list) else data.get("data", [])
        for t in trades:
            size = float(t.get("size", 0) or 0)
            is_short = str(t.get("side", "")).lower() in ("short", "sell", "s")
            total_vol += size
            if is_short:
                short_vol += size

    ratio = short_vol / total_vol if total_vol > 0 else None
    return [MetricReading(name="uw_darkpool_short", factor="S", raw_value=ratio,
                          direction=Direction.BEARISH_HIGH,
                          source="UnusualWhales:darkpool", asof=now,
                          note=f"short_vol={short_vol:,.0f} / total={total_vol:,.0f}"
                               if total_vol else "no dark pool data")]


# --------------------------------------------------------------------------- #
# Market summary → GEX + retail streak
# --------------------------------------------------------------------------- #
def fetch_market_summary() -> list[MetricReading]:
    now = dt.datetime.utcnow()
    data = _get("/api/market/summary")
    if not data:
        return [
            MetricReading(name="uw_gex_total", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="UnusualWhales:market/summary",
                          asof=now, note="market summary pull failed"),
            MetricReading(name="retail_call_streak", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="UnusualWhales:market/summary",
                          asof=now, note="market summary pull failed"),
        ]
    d = data if not isinstance(data, list) else (data[0] if data else {})
    gex = float(d.get("gex", 0) or d.get("total_gex", 0) or 0)
    streak = float(d.get("retail_call_streak_weeks", 0) or d.get("streak", 0) or 0)

    return [
        MetricReading(name="uw_gex_total", factor="S", raw_value=gex,
                      direction=Direction.BEARISH_HIGH,   # negative GEX = amplifier = more bearish
                      source="UnusualWhales:market/summary", asof=now,
                      note=f"signed GEX={gex:+.2e}; negative dealer short gamma"),
        MetricReading(name="retail_call_streak", factor="S", raw_value=streak,
                      direction=Direction.BEARISH_HIGH,
                      source="UnusualWhales:market/summary", asof=now,
                      note=f"consecutive weeks net-call-buying = {streak:.0f}"),
    ]


def fetch_all(basket: list[str]) -> list[MetricReading]:
    out = []
    out.extend(fetch_flow_metrics(basket))
    out.extend(fetch_darkpool_metrics(basket))
    out.extend(fetch_market_summary())
    return out


if __name__ == "__main__":
    BASKET = ["NVDA", "MU", "MSFT", "GOOGL", "AMD"]
    try:
        metrics = fetch_all(BASKET)
        for m in metrics:
            val = f"{m.raw_value:.4f}" if m.raw_value is not None else "MISSING"
            print(f"  {m.name:28s} {val:12s} | {m.note}")
    except EnvironmentError as e:
        print(f"  {e} — set UW_API_KEY in .env")
