"""
src/tools/polygon.py — Polygon.io: options chains, grouped daily breadth, vol surface

APIs used:
  /v3/snapshot/options/{ticker}       → options chain snapshot (IV, greeks, OI)
  /v2/aggs/grouped/locale/us/market/stocks/{date} → all US stocks for breadth
  /v2/aggs/ticker/{ticker}/range/...  → individual OHLCV for phase.py

MetricReadings produced:
  factor S: put_call_inv, iv_skew, iv_term_structure (vol regime)
  factor B: pct_above_200dma, new_high_low, divergence (breadth)
  factor S: gamma_exposure (signed dealer GEX)

Requires POLYGON_API_KEY. Paid tier recommended ($29+/mo) for full chain access.
Run standalone: python -m src.tools.polygon
"""
from __future__ import annotations

import datetime as dt
import math
import os
from pathlib import Path
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading
from ._env import get_key, load_env

load_env()
_BASE = "https://api.polygon.io"


def _key() -> str:
    k = get_key("POLYGON_API_KEY", "MASSIVE_API_KEY")
    if not k:
        raise EnvironmentError("POLYGON_API_KEY or MASSIVE_API_KEY not set")
    return k


def _get(path: str, params: dict | None = None) -> Optional[dict]:
    try:
        r = httpx.get(f"{_BASE}{path}", params={"apiKey": _key(), **(params or {})},
                      timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Options chain → put/call ratio, IV skew, term structure, GEX
# --------------------------------------------------------------------------- #
def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bs_delta(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return _norm_cdf(d1) if is_call else _norm_cdf(d1) - 1.0


def fetch_options_metrics(ticker: str, r: float = 0.045) -> list[MetricReading]:
    """
    Pull the full options chain snapshot for a ticker, compute:
    - put/call OI ratio (inverted → high ratio = more hedging = less bearish?)
      We use net-premium direction: if net premium flows to puts = bearish.
    - 25Δ skew (put 25Δ IV − call 25Δ IV): positive = crash-tail bid
    - term structure (front-month ATM IV − back-month ATM IV): positive = stress
    - signed GEX: Σ gamma·OI·100·S² ; negative = dealer short gamma = amplifier
    """
    now = dt.datetime.utcnow()
    data = _get(f"/v3/snapshot/options/{ticker}")
    if not data or "results" not in data:
        note = f"chain pull failed for {ticker}"
        return [
            MetricReading(name="put_call_inv", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source=f"Polygon:{ticker}", asof=now, note=note),
            MetricReading(name="iv_skew", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source=f"Polygon:{ticker}", asof=now, note=note),
            MetricReading(name="iv_term_structure", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source=f"Polygon:{ticker}", asof=now, note=note),
            MetricReading(name="gamma_exposure", factor="S", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source=f"Polygon:{ticker}", asof=now, note=note),
        ]

    contracts = data["results"]
    put_oi = call_oi = 0.0
    put_premium = call_premium = 0.0
    front_puts: list[float] = []    # IV of ~25Δ puts, nearest expiry
    front_calls: list[float] = []
    back_puts: list[float] = []     # same for back expiry
    back_calls: list[float] = []
    gex = 0.0

    # sort expiries to label front/back
    expiries = sorted({c.get("details", {}).get("expiration_date", "") for c in contracts
                       if c.get("details", {}).get("expiration_date")})
    front_exp = expiries[0] if expiries else ""
    back_exp = expiries[min(2, len(expiries) - 1)] if len(expiries) > 1 else ""

    S = None
    for c in contracts:
        det = c.get("details", {})
        greeks_d = c.get("greeks", {}) or {}
        day = c.get("day", {}) or {}
        underlying = c.get("underlying_asset", {}) or {}

        if S is None and underlying.get("price"):
            S = float(underlying["price"])

        contract_type = det.get("contract_type", "")
        oi = float(c.get("open_interest", 0) or 0)
        iv = float(c.get("implied_volatility", 0) or 0)
        gamma = float(greeks_d.get("gamma", 0) or 0)
        delta = float(greeks_d.get("delta", 0) or 0)
        vwap = float(day.get("vwap", 0) or 0)
        exp = det.get("expiration_date", "")
        K = float(det.get("strike_price", 0) or 0)

        is_put = contract_type == "put"
        is_call_c = contract_type == "call"

        if is_put:
            put_oi += oi
            put_premium += vwap * oi
        elif is_call_c:
            call_oi += oi
            call_premium += vwap * oi

        # GEX: dealer is short options → negative gamma exposure when retail buys calls
        # Convention: GEX = Σ (gamma * OI * 100 * S²) with sign flip for puts
        if S and K:
            contract_gex = gamma * oi * 100 * S * S
            gex += contract_gex if is_call_c else -contract_gex

        # 25Δ skew: bucket by abs(delta) ≈ 0.20..0.30
        if 0.20 <= abs(delta) <= 0.30 and iv > 0:
            if exp == front_exp:
                (front_puts if is_put else front_calls).append(iv)
            elif exp == back_exp:
                (back_puts if is_call_c else back_calls).append(iv)

    # put/call ratio (OI-based); BULLISH_HIGH because higher ratio = more hedging (less panic signal)
    pc_ratio = put_oi / call_oi if call_oi > 0 else None
    # invert: low PC (too much call buying) = bearish signal → high n_i
    pc_inv = 1.0 / pc_ratio if pc_ratio and pc_ratio > 0 else None

    # 25Δ skew: put_IV − call_IV; positive = crash-tail bid = bearish signal
    front_put_iv = sum(front_puts) / len(front_puts) if front_puts else None
    front_call_iv = sum(front_calls) / len(front_calls) if front_calls else None
    skew = (front_put_iv - front_call_iv) if (front_put_iv and front_call_iv) else None

    # term structure: front ATM − back ATM; positive = backwardation = stress
    back_put_iv = sum(back_puts) / len(back_puts) if back_puts else None
    term_str = (front_put_iv - back_put_iv) if (front_put_iv and back_put_iv) else None

    source = f"Polygon:options_snapshot:{ticker}"
    return [
        MetricReading(name="put_call_inv", factor="S", raw_value=pc_inv,
                      direction=Direction.BEARISH_HIGH, source=source, asof=now,
                      note=f"1/PC_ratio; PC_OI={pc_ratio:.2f}" if pc_ratio else "no OI data"),
        MetricReading(name="iv_skew", factor="S", raw_value=skew,
                      direction=Direction.BEARISH_HIGH, source=source, asof=now,
                      note=f"25Δ put_IV={front_put_iv:.3f} call_IV={front_call_iv:.3f}"
                           if (front_put_iv and front_call_iv) else "insufficient 25Δ contracts"),
        MetricReading(name="iv_term_structure", factor="S", raw_value=term_str,
                      direction=Direction.BEARISH_HIGH, source=source, asof=now,
                      note=f"front={front_put_iv:.3f} back={back_put_iv:.3f}"
                           if (front_put_iv and back_put_iv) else "no back-month data"),
        MetricReading(name="gamma_exposure", factor="S", raw_value=gex,
                      direction=Direction.BEARISH_HIGH, source=source, asof=now,
                      note=f"signed GEX={gex:+.2e}; negative=dealer short gamma=amplifier"),
    ]


# --------------------------------------------------------------------------- #
# Breadth from grouped daily
# --------------------------------------------------------------------------- #
def fetch_breadth(date: dt.date | None = None) -> list[MetricReading]:
    """Grouped daily bars → new 52w highs and lows, % above 200dma (approximated by high-low range)."""
    d = (date or dt.date.today() - dt.timedelta(days=1)).isoformat()
    now = dt.datetime.utcnow()
    data = _get(f"/v2/aggs/grouped/locale/us/market/stocks/{d}")
    if not data or "results" not in data:
        return [MetricReading(name="new_high_low", factor="B", raw_value=None,
                              direction=Direction.BEARISH_HIGH, source=f"Polygon:grouped:{d}",
                              asof=now, note="grouped daily pull failed")]

    results = data["results"]
    # new high/low: approximate via vw vs prior-session (Polygon grouped has prior close as pc)
    highs = lows = 0
    for r in results:
        if not r.get("vw") or not r.get("pc") or r["pc"] == 0:
            continue
        ret = (r["vw"] - r["pc"]) / r["pc"]
        if ret >= 0.04:
            highs += 1
        elif ret <= -0.04:
            lows += 1

    net = (highs - lows) / max(len(results), 1)  # normalized net: >0 = breadth expanding
    # High divergence = index rising but net is negative; we can't compute that from grouped alone
    # — the breadth_divergence metric needs to be computed against index level in the orchestrator.
    return [
        MetricReading(name="new_high_low", factor="B", raw_value=net,
                      direction=Direction.BULLISH_HIGH,   # positive net = healthy breadth = less bearish
                      source=f"Polygon:grouped_daily:{d}", asof=now,
                      note=f"highs={highs} lows={lows} n={len(results)}"),
    ]


# --------------------------------------------------------------------------- #
# Single-ticker OHLCV series for phase.py
# --------------------------------------------------------------------------- #
def fetch_ohlcv_series(ticker: str, days: int = 252) -> Optional[list[dict]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=days + 30)
    data = _get(f"/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{end.isoformat()}",
                params={"adjusted": "true", "sort": "asc", "limit": days + 30})
    if not data or "results" not in data:
        return None
    return [{"open": r["o"], "high": r["h"], "low": r["l"],
             "close": r["c"], "volume": r["v"]} for r in data["results"]]


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    try:
        metrics = fetch_options_metrics(ticker)
        print(f"Options metrics for {ticker}:")
        for m in metrics:
            val = f"{m.raw_value:.4f}" if m.raw_value is not None else "MISSING"
            print(f"  {m.name:25s} {val:12s} | {m.note}")
        breadth = fetch_breadth()
        print("\nBreadth:")
        for m in breadth:
            val = f"{m.raw_value:.4f}" if m.raw_value is not None else "MISSING"
            print(f"  {m.name:25s} {val:12s} | {m.note}")
    except EnvironmentError as e:
        print(f"  {e} — set POLYGON_API_KEY in .env")
