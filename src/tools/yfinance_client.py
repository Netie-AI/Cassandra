"""
src/tools/yfinance_client.py — yfinance: US OHLCV, breadth, index (CORE — no key needed)

Role in routing: PRIMARY source for Market Structure (factor B) and phase.py OHLCV.
Free, reliable, no rate limit issues. Use before Polygon for all price/breadth needs.

MetricReadings (factor B):
  pct_above_200dma        — breadth health (BULLISH_HIGH → inverted at normalize)
  new_high_low            — net new highs minus lows, normalised (-1..+1)
  index_breadth_divergence— key distribution tell: index at high while breadth weak

Also: saves OHLCV CSV for the phase classifier and returns the path.
Run standalone: python -m src.tools.yfinance_client
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import numpy as np

from ..schemas import Direction, MetricReading
from ._env import load_env

load_env()
_STORE = Path(__file__).resolve().parent.parent.parent / "store" / "ohlcv"
_STORE.mkdir(parents=True, exist_ok=True)


def _yf():
    try:
        import yfinance as yf
        return yf
    except ImportError:
        raise ImportError("pip install yfinance")


def fetch_ohlcv(symbol: str, period: str = "2y") -> Optional[dict]:
    """
    Pull daily OHLCV for one symbol. Returns dict with 'df' (pandas DataFrame) and 'csv_path'.
    Saves to store/ohlcv/<symbol>.csv for phase.py consumption.
    """
    yf = _yf()
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d", auto_adjust=True)
        if df.empty:
            return None
        df.index = df.index.tz_localize(None)   # remove tz for clean CSV
        df.columns = [c.lower() for c in df.columns]
        csv_path = _STORE / f"{symbol}.csv"
        df[["open", "high", "low", "close", "volume"]].to_csv(csv_path)
        return {"df": df, "csv_path": str(csv_path), "symbol": symbol}
    except Exception:
        return None


def fetch_breadth(basket: list[str], index_symbol: str = "^GSPC") -> list[MetricReading]:
    """
    For each symbol in basket: check if price > 200dma.
    Also fetches index level to compute breadth-divergence vs index.
    Returns MetricReadings for factor B.
    """
    yf = _yf()
    now = dt.datetime.utcnow()
    above = 0
    total = 0
    rets: list[float] = []   # 1-day returns for new-high-low proxy

    for sym in basket:
        data = fetch_ohlcv(sym)
        if not data:
            continue
        df = data["df"]
        if len(df) < 200:
            continue
        close = df["close"]
        ma200 = close.rolling(200).mean().iloc[-1]
        last = close.iloc[-1]
        total += 1
        if last > ma200:
            above += 1
        # 1-day return for new-high proxy
        if len(close) >= 2:
            rets.append((last - close.iloc[-2]) / close.iloc[-2])

    pct = above / total if total else None

    # new_high_low proxy: fraction of basket with positive 1d return minus negative
    if rets:
        n_up = sum(1 for r in rets if r > 0.02)
        n_dn = sum(1 for r in rets if r < -0.02)
        nhl = (n_up - n_dn) / len(rets)
    else:
        nhl = None

    # breadth divergence: index near highs while pct_above_200dma is weak
    divergence = None
    idx_data = fetch_ohlcv(index_symbol)
    if idx_data and pct is not None:
        idx_close = idx_data["df"]["close"]
        if len(idx_close) >= 52 * 5:  # ~1 year of trading days
            idx_52w_pct = (idx_close.iloc[-1] - idx_close.iloc[-252]) / idx_close.iloc[-252]
            # divergence: index up over year while breadth <60% → positive divergence = bearish
            divergence = max(0.0, min(1.0, idx_52w_pct - (pct - 0.5)))
        else:
            divergence = None

    note_pct = f"{above}/{total} above 200dma = {pct*100:.1f}%" if pct is not None else "no data"
    return [
        MetricReading(name="pct_above_200dma", factor="B", raw_value=pct,
                      direction=Direction.BULLISH_HIGH,   # high pct = healthy = less bearish (inverted)
                      source=f"yfinance:{','.join(basket[:5])}...", asof=now, note=note_pct),
        MetricReading(name="new_high_low", factor="B", raw_value=nhl,
                      direction=Direction.BULLISH_HIGH,
                      source=f"yfinance:{','.join(basket[:5])}...", asof=now,
                      note=f"net daily mover fraction={nhl:.2f}" if nhl is not None else "no data"),
        MetricReading(name="divergence", factor="B", raw_value=divergence,
                      direction=Direction.BEARISH_HIGH,
                      source=f"yfinance:{index_symbol}+basket", asof=now,
                      note=f"divergence={divergence:.2f}" if divergence is not None else "no data"),
    ]


def get_index_ohlcv_path(index_symbol: str = "^GSPC") -> Optional[str]:
    """Return the CSV path for the index, pulling fresh if needed. Used by phase.py."""
    data = fetch_ohlcv(index_symbol)
    return data["csv_path"] if data else None


if __name__ == "__main__":
    BASKET = ["NVDA", "MU", "MSFT", "AMD", "AVGO", "GOOGL", "META", "TSM", "AMAT", "CRDO"]
    print("Fetching breadth for semis+tech basket...")
    metrics = fetch_breadth(BASKET)
    for m in metrics:
        val = f"{m.raw_value:.3f}" if m.raw_value is not None else "MISSING"
        print(f"  {m.name:30s} {val:10s} {m.note}")
    print("\nIndex OHLCV path:", get_index_ohlcv_path())
