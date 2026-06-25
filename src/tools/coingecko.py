"""
src/tools/coingecko.py — CoinGecko: BTC/crypto crossread for factor S (Sentiment)

Role in routing: CORE crypto crossread when feature.enable_crypto_crossread = true.
Key: COINGECKO_API_KEY (demo key works; Pro unlocks higher rate limits).
Free demo: 30 calls/min. Cache aggressively.

MetricReadings (factor S):
  crypto_mvrv    — BTC price / 200dma-price as MVRV proxy (use_percentile=True; BEARISH_HIGH)
  crypto_nupl    — NUPL proxy: (price-200dma)/price  (positive = most holders in profit)
  survey         — Fear & Greed index from alternative.me (0=fear, 100=greed; BEARISH_HIGH)

Note: True MVRV-Z / NUPL require Glassnode (realized cap). These are BTC-price-derived proxies.
They are secondary confirmation signals, not primary drivers (weight 0.15 in S).
Run standalone: python -m src.tools.coingecko
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading
from ._env import get_key, load_env

load_env()
_CG_BASE = "https://api.coingecko.com/api/v3"
_CG_PRO  = "https://pro-api.coingecko.com/api/v3"
_FNG_URL = "https://api.alternative.me/fng/"
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "store" / "cache" / "coingecko"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key() -> Optional[str]:
    return get_key("COINGECKO_API_KEY") or None


def _base() -> str:
    return _CG_PRO if _key() else _CG_BASE


def _headers() -> dict:
    k = _key()
    return {"x-cg-demo-api-key": k} if k else {}


def _get(path: str, params: dict | None = None, cache_hours: float = 4) -> Optional[dict | list]:
    import json, time
    cache_key = path.replace("/", "_") + str(sorted((params or {}).items()))
    cp = _CACHE_DIR / (cache_key[:80] + ".json")
    if cp.exists() and (time.time() - cp.stat().st_mtime) < cache_hours * 3600:
        return json.loads(cp.read_text())
    try:
        r = httpx.get(f"{_base()}{path}", headers=_headers(), params=params or {}, timeout=20)
        r.raise_for_status()
        data = r.json()
        cp.write_text(json.dumps(data))
        return data
    except Exception:
        return None


def _btc_price_series(days: int = 365) -> Optional[list[float]]:
    """BTC daily close prices for the last N days."""
    data = _get("/coins/bitcoin/market_chart", {"vs_currency": "usd", "days": str(days), "interval": "daily"})
    if not data or "prices" not in data:
        return None
    return [p[1] for p in data["prices"]]


def _fear_greed() -> Optional[float]:
    """Alternative.me Fear & Greed index, 0=extreme fear, 100=extreme greed."""
    try:
        r = httpx.get(_FNG_URL, params={"limit": 1}, timeout=10)
        r.raise_for_status()
        d = r.json()
        return float(d["data"][0]["value"])
    except Exception:
        return None


def fetch() -> list[MetricReading]:
    now = dt.datetime.utcnow()
    prices = _btc_price_series(365)

    if not prices or len(prices) < 200:
        note = "insufficient BTC price history"
        return [
            MetricReading(name="crypto_mvrv", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="CoinGecko:BTC",
                          asof=now, use_percentile=True, hard_threshold=7.0, note=note),
            MetricReading(name="crypto_nupl", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="CoinGecko:BTC", asof=now, note=note),
            MetricReading(name="survey", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="alternative.me:FNG", asof=now, note=note),
        ]

    import numpy as np
    arr = np.asarray(prices, dtype=float)
    last = arr[-1]
    ma200 = float(arr[-200:].mean())

    # MVRV proxy: current price / 200dma (stands in for price/realised_price)
    mvrv_proxy = last / ma200 if ma200 > 0 else None

    # NUPL proxy: (price - 200dma) / price → positive = majority in profit
    nupl_proxy = (last - ma200) / last if last > 0 else None

    # Fear & Greed (from alternative.me — separate source)
    fg = _fear_greed()
    fg_normalized = fg / 100.0 if fg is not None else None   # 0..1, high = greed = bearish

    return [
        MetricReading(
            name="crypto_mvrv", factor="S", raw_value=mvrv_proxy,
            direction=Direction.BEARISH_HIGH,
            source="CoinGecko:bitcoin/market_chart", asof=now,
            use_percentile=True, hard_threshold=7.0,   # §2: use percentile + MVRV>7 historical top
            note=f"BTC_price/200dma_proxy={mvrv_proxy:.3f} (true MVRV needs Glassnode realized cap)"
        ),
        MetricReading(
            name="crypto_nupl", factor="S", raw_value=nupl_proxy,
            direction=Direction.BEARISH_HIGH,
            source="CoinGecko:bitcoin/market_chart", asof=now,
            note=f"NUPL_proxy=(price-200dma)/price={nupl_proxy:.3f}"
        ),
        MetricReading(
            name="survey", factor="S", raw_value=fg_normalized,
            direction=Direction.BEARISH_HIGH,
            source="alternative.me:FNG", asof=now,
            note=f"Fear&Greed={fg:.0f}/100 (100=extreme greed=bearish)" if fg else "F&G pull failed"
        ),
    ]


if __name__ == "__main__":
    metrics = fetch()
    for m in metrics:
        val = f"{m.raw_value:.4f}" if m.raw_value is not None else "MISSING"
        print(f"  {m.name:20s} {val:12s} pct={m.use_percentile}  | {m.note}")
