"""
src/tools/alpaca.py — Alpaca Market Data (free paper account)

Sign up at alpaca.markets; paper keys give free US equity bars.
Docs: https://github.com/alpacahq/alpaca-py

ENV: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER=true (default)

Run: python -m src.tools.alpaca NVDA
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading
from ._env import get_key, load_env

load_env()
_DATA = "https://data.alpaca.markets"
_SANDBOX = "https://data.sandbox.alpaca.markets"


def _headers() -> dict:
    key = get_key("ALPACA_API_KEY", "APCA_API_KEY_ID")
    secret = get_key("ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")
    if not key or not secret:
        raise EnvironmentError("ALPACA_API_KEY and ALPACA_SECRET_KEY not set")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def _base() -> str:
    import os
    paper = os.environ.get("ALPACA_PAPER", "true").lower() != "false"
    return _SANDBOX if paper else _DATA


def fetch_bars(symbol: str, days: int = 30) -> Optional[list[dict]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=days + 5)
    try:
        r = httpx.get(
            f"{_base()}/v2/stocks/{symbol}/bars",
            headers=_headers(),
            params={"timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(),
                    "limit": days + 10, "adjustment": "split"},
            timeout=30,
        )
        r.raise_for_status()
        bars = r.json().get("bars") or []
        return [{"close": b["c"], "volume": b["v"], "date": b["t"][:10]} for b in bars]
    except Exception:
        return None


def fetch_quote(symbol: str) -> list[MetricReading]:
    now = dt.datetime.now(dt.timezone.utc)
    bars = fetch_bars(symbol, days=5)
    if not bars:
        return [MetricReading(name="alpaca_close", factor="B", raw_value=None,
                                direction=Direction.BEARISH_HIGH, source=f"Alpaca:{symbol}",
                                asof=now, note="bar pull failed — check Alpaca keys")]
    close = float(bars[-1]["close"])
    return [MetricReading(name="alpaca_close", factor="B", raw_value=close,
                          direction=Direction.BEARISH_HIGH, source=f"Alpaca:{symbol}",
                          asof=now, note=f"latest close={close:.2f}")]


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    try:
        for m in fetch_quote(sym):
            val = f"{m.raw_value:.2f}" if m.raw_value else "MISSING"
            print(f"  {sym} close={val} | {m.note}")
    except EnvironmentError as e:
        print(f"  {e} — get free paper keys at alpaca.markets")
