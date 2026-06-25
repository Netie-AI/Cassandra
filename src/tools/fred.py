"""
tools/fred.py — example API client. Copy this pattern for every source.

Contract: a client pulls raw data and returns a list[MetricReading] tagged with factor + direction +
source + asof. It does NOT normalize (the orchestrator does that against history) and does NOT score.
This keeps every source uniform and the scorer source-agnostic.
"""
from __future__ import annotations

import datetime as dt
import os

import httpx

from ..schemas import Direction, MetricReading

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _latest(series_id: str) -> tuple[float, dt.datetime] | tuple[None, dt.datetime]:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None, dt.datetime.utcnow()
    params = {"series_id": series_id, "api_key": key, "file_type": "json",
              "sort_order": "desc", "limit": 1}
    try:
        r = httpx.get(FRED_BASE, params=params, timeout=20)
        r.raise_for_status()
        obs = r.json()["observations"][0]
        return float(obs["value"]), dt.datetime.fromisoformat(obs["date"])
    except Exception:
        return None, dt.datetime.utcnow()


def fetch() -> list[MetricReading]:
    """Pull the FRED-sourced metrics that feed factors L, V, and C."""
    out: list[MetricReading] = []

    # HY OAS credit spread -> Leverage (tight spread = complacency; direction handled at normalize via inv name)
    val, asof = _latest("BAMLH0A0HYM2")        # ICE BofA US High Yield OAS
    out.append(MetricReading(
        name="credit_spread_inv", factor="L", raw_value=val, direction=Direction.BULLISH_HIGH,
        source="FRED:BAMLH0A0HYM2", asof=asof,
        note="HY OAS; tight spread = fragile, so BULLISH_HIGH (sign-flipped at normalize)" if val else "pull failed",
    ))

    # 10y real rate -> a macro liquidity/trigger input
    val, asof = _latest("DFII10")              # 10Y TIPS yield
    out.append(MetricReading(
        name="net_liquidity", factor="C", raw_value=val, direction=Direction.BEARISH_HIGH,
        source="FRED:DFII10", asof=asof,
        note="real rate proxy; higher = tighter = more bearish" if val else "pull failed",
    ))

    # Wilshire 5000 / GDP (market-cap-to-GDP, the Buffett indicator) -> Valuation
    mcap, a1 = _latest("WILL5000PRFC")
    gdp, a2 = _latest("GDP")
    ratio = (mcap / gdp) if (mcap and gdp) else None
    out.append(MetricReading(
        name="mktcap_gdp", factor="V", raw_value=ratio, direction=Direction.BEARISH_HIGH,
        source="FRED:WILL5000PRFC/GDP", asof=min(a1, a2),
        note="Buffett indicator" if ratio else "pull failed",
    ))

    return out


if __name__ == "__main__":
    for m in fetch():
        print(f"{m.name:20s} factor={m.factor} raw={m.raw_value} src={m.source} note={m.note}")
