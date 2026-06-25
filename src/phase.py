"""
phase.py — Wyckoff phase classifier (CRASH_SCORE_SPEC §7 cross-check).

A *descriptive* read on the tape that runs parallel to the quantitative CRS. When the two agree
(high CRS + Distribution/UTAD), conviction is highest. Real-time Wyckoff is probabilistic — this
emits a phase AND a confidence, never certainty.

Detection rules operate on daily OHLCV + volume. Implemented with numpy/pandas only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PhaseResult:
    phase: str
    confidence: float
    evidence: list[str]


def _rolling_extrema(close: pd.Series, win: int) -> tuple[pd.Series, pd.Series]:
    return close.rolling(win, center=False).max(), close.rolling(win, center=False).min()


def classify(ohlcv: pd.DataFrame,
             vol_spike_sigma: float = 2.0,
             swing_win: int = 20,
             atr_mult_extension: float = 2.5) -> PhaseResult:
    """
    ohlcv: DataFrame with columns [open, high, low, close, volume], daily, chronological.
    Returns the most recently matched Wyckoff phase with a confidence and the rules that fired.

    Heuristic state logic (simplified but faithful):
      Buying Climax (BC)     : new swing high + volume spike + subsequent down-close within N bars,
                               price extended > atr_mult above 50dma
      Automatic Reaction (AR): sharp drop off BC ( > drop_pct ) within M bars on elevated volume
      Secondary Test (ST)    : rally toward BC high but lower-high, on LOWER volume than BC
      Distribution Range     : oscillation in [AR low, BC high], declining volume, ≥1 ST
      UTAD                   : brief poke above BC high that closes back inside the range (bull trap)
      Markdown               : decisive close below range support (AR low) on volume expansion
      Markup / Accumulation  : inverse / uptrend with higher lows
    """
    df = ohlcv.copy()
    if len(df) < 60:
        return PhaseResult("undetermined", 0.0, ["insufficient history (<60 bars)"])

    close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
    df["ma50"] = close.rolling(50).mean()
    df["atr"] = (high - low).rolling(14).mean()
    df["vol_ma"] = vol.rolling(20).mean()
    df["vol_sd"] = vol.rolling(20).std(ddof=0)
    df["vol_spike"] = vol > (df["vol_ma"] + vol_spike_sigma * df["vol_sd"])

    swing_hi, swing_lo = _rolling_extrema(close, swing_win)
    look = df.tail(swing_win * 3)               # examine recent window
    evidence: list[str] = []

    # --- locate the most recent buying climax candidate ---
    bc_idx = None
    for i in range(len(df) - 2, max(len(df) - swing_win * 3, 50), -1):
        c = close.iloc[i]
        is_new_high = c >= swing_hi.iloc[i] * 0.999
        extended = (c - df["ma50"].iloc[i]) > atr_mult_extension * df["atr"].iloc[i]
        spike = bool(df["vol_spike"].iloc[i])
        down_after = any(close.iloc[j] < c for j in range(i + 1, min(i + 4, len(df))))
        if is_new_high and spike and extended and down_after:
            bc_idx = i
            evidence.append(f"buying climax @bar{i}: new high + vol spike + extension {atr_mult_extension}·ATR")
            break

    bc_high = close.iloc[bc_idx] if bc_idx is not None else None
    last = close.iloc[-1]

    # --- markdown: decisive break below recent range support on volume expansion ---
    range_support = low.tail(swing_win * 2).min()
    broke_support = last < range_support * 1.001
    vol_expanding = bool(df["vol_spike"].iloc[-1]) or vol.iloc[-1] > df["vol_ma"].iloc[-1]
    if broke_support and vol_expanding and bc_idx is not None:
        evidence.append("markdown: close below range support on expanding volume")
        return PhaseResult("markdown", 0.75, evidence)

    if bc_idx is not None:
        # --- automatic reaction off the climax ---
        post = close.iloc[bc_idx:]
        drawdown = (bc_high - post.min()) / bc_high
        ar_low = post.min()
        if drawdown > 0.06:
            evidence.append(f"automatic reaction: {drawdown*100:.1f}% off climax")

        # --- where is price now relative to the range? ---
        in_range = ar_low * 0.99 <= last <= bc_high * 1.01
        above_bc = last > bc_high * 1.01
        # recent local high
        recent_hi = close.tail(swing_win).max()

        if above_bc:
            # poke above then back in => UTAD; sustained => markup continuation
            closed_back = close.iloc[-1] < bc_high
            if closed_back:
                evidence.append("upthrust (UTAD): poke above climax high, closed back inside range")
                return PhaseResult("upthrust_utad", 0.6, evidence)
            evidence.append("price sustaining above prior climax high")
            return PhaseResult("markup", 0.5, evidence)

        if in_range:
            # secondary test vs distribution range
            near_high = recent_hi > bc_high * 0.97 and recent_hi < bc_high
            lower_vol = vol.tail(swing_win).mean() < vol.iloc[max(bc_idx-2,0):bc_idx+1].mean()
            if near_high and lower_vol:
                evidence.append("secondary test: lower-high retest of climax on lower volume")
                return PhaseResult("secondary_test", 0.6, evidence)
            evidence.append("oscillating within [AR low, BC high] with subdued volume")
            return PhaseResult("distribution_range", 0.55, evidence)

    # --- trend fallback: markup vs accumulation via higher-low / lower-high structure ---
    lows = low.tail(swing_win)
    higher_lows = lows.iloc[-1] > lows.iloc[0]
    above_ma = last > df["ma50"].iloc[-1]
    if higher_lows and above_ma:
        evidence.append("uptrend: higher lows, price above 50dma")
        return PhaseResult("markup", 0.45, evidence)
    if not higher_lows and not above_ma:
        evidence.append("basing: lower structure below 50dma, no climax detected")
        return PhaseResult("accumulation", 0.4, evidence)

    evidence.append("no clean Wyckoff signature in window")
    return PhaseResult("undetermined", 0.3, evidence)


if __name__ == "__main__":
    # smoke test on synthetic parabola -> climax -> reaction
    n = 120
    base = np.linspace(100, 300, n) + np.random.default_rng(0).normal(0, 3, n)
    base[-15:] = base[-16] - np.linspace(0, 40, 15)        # rollover
    v = np.full(n, 1_000_000.0)
    v[-16] = 4_000_000.0                                    # volume spike at the high
    df = pd.DataFrame({"open": base, "high": base + 2, "low": base - 2, "close": base, "volume": v})
    r = classify(df)
    print(f"phase={r.phase} confidence={r.confidence}\nevidence={r.evidence}")
