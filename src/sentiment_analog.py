"""
sentiment_analog.py — "which crash, and how many months before it, does today resemble?"

Builds a feature vector for today (sentiment + the CRS factors), measures its distance to labeled
days inside historical pre-crash windows, and reports the nearest analog as "today tracks ~T-minus N
days before <event>." The daily estimate is noisy, so it is Gaussian-smoothed. When reality later
diverges from the analog, an error-attribution loop logs WHY (regime difference) and down-weights the
misleading analog.

READ THIS BEFORE TRUSTING IT — the epistemics are weak by construction:
  - n is tiny. There are ~3-4 usable historical crashes. High-dim features over 3 samples is the
    curse of dimensionality; the "T-minus N days" number is an ESTIMATE WITH A WIDE BAND, not a clock.
  - Analogies break on regime change. 2026 hyperscalers are cash-rich; 2000 dot-coms were not. The
    module's job is to FLAG resemblance and force you to ask "is the difference load-bearing?", never
    to count down to a date. Treat divergence as information, not failure.

Run `python -m src.sentiment_analog` for the self-test.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

# Feature order is fixed across today and all historical vectors.
FEATURES = ["news_sentiment", "put_call", "pct_above_200dma", "vix_level",
            "margin_yoy", "cohort_fwd_ps_z", "capex_cut_signal", "breadth_divergence"]


@dataclass
class AnalogDay:
    event: str                  # "cisco_2000", "gfc_2008", "top_2021"
    days_before_peak: int       # 0 = the peak day; 90 = three months before
    vec: np.ndarray             # normalized feature vector
    weight: float = 1.0         # down-weighted by the error loop when it misleads


@dataclass
class AnalogResult:
    nearest_event: str
    est_days_before: float      # smoothed estimate
    est_days_raw: float         # today's raw estimate (pre-smoothing)
    band_days: float            # uncertainty half-width
    confidence: float
    regime_warnings: list[str] = field(default_factory=list)


def normalize(vec: dict[str, float], baseline_mu: dict[str, float],
              baseline_sd: dict[str, float]) -> np.ndarray:
    out = []
    for f in FEATURES:
        mu, sd = baseline_mu.get(f, 0.0), baseline_sd.get(f, 1.0) or 1.0
        out.append((vec.get(f, mu) - mu) / sd)
    return np.asarray(out, dtype=float)


def _distance(a: np.ndarray, b: np.ndarray, inv_cov: np.ndarray | None = None) -> float:
    d = a - b
    if inv_cov is not None:                       # Mahalanobis if a covariance is supplied
        return float(math.sqrt(max(d @ inv_cov @ d, 0)))
    return float(np.linalg.norm(d))               # else Euclidean


def estimate_today(today_vec: np.ndarray, library: list[AnalogDay],
                   k: int = 8, inv_cov: np.ndarray | None = None) -> tuple[str, float, float]:
    """k-NN over the historical library. Returns (event, est_days_before, spread)."""
    scored = []
    for a in library:
        dist = _distance(today_vec, a.vec, inv_cov)
        sim = a.weight / (1e-6 + dist)            # inverse-distance, weighted
        scored.append((sim, a))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:k]
    sims = np.array([s for s, _ in top])
    days = np.array([a.days_before_peak for _, a in top], dtype=float)
    w = sims / sims.sum()
    est = float((w * days).sum())
    spread = float(math.sqrt((w * (days - est) ** 2).sum()))
    # nearest event = modal event among the top-k (weighted)
    ev_w: dict[str, float] = {}
    for s, a in top:
        ev_w[a.event] = ev_w.get(a.event, 0.0) + s
    nearest = max(ev_w, key=ev_w.get)
    return nearest, est, spread


def gaussian_smooth(series: list[float], sigma: float = 3.0) -> float:
    """Gaussian-kernel smooth of the recent daily estimates; returns the smoothed latest value."""
    x = np.asarray(series, dtype=float)
    if x.size == 0:
        return float("nan")
    n = x.size
    idx = np.arange(n)
    center = n - 1
    w = np.exp(-0.5 * ((idx - center) / sigma) ** 2)
    w /= w.sum()
    return float((w * x).sum())


def assess(today_raw: dict[str, float],
           baseline_mu: dict[str, float], baseline_sd: dict[str, float],
           library: list[AnalogDay], recent_raw_estimates: list[float],
           regime_flags: dict[str, bool] | None = None) -> AnalogResult:
    vec = normalize(today_raw, baseline_mu, baseline_sd)
    nearest, est_raw, spread = estimate_today(vec, library)
    smoothed = gaussian_smooth(recent_raw_estimates + [est_raw])

    # regime warnings make the analogy honest
    warnings = []
    rf = regime_flags or {}
    if rf.get("hyperscalers_cashrich"):
        warnings.append("2026 buyers fund capex from cash flow; 2000 dot-coms did not — analog may overstate fragility")
    if rf.get("rates_regime_differs"):
        warnings.append("rate path differs from the analog's — discounting dynamics not comparable")
    if rf.get("etf_structural_bid"):
        warnings.append("passive/ETF structural bid absent in older analogs — tops can stretch longer")

    # confidence shrinks with spread (disagreement among neighbors) and number of regime warnings
    conf = max(0.0, min(1.0, 1.0 - spread / 120.0 - 0.1 * len(warnings)))
    band = spread + 10 * len(warnings)            # band widens with regime risk
    return AnalogResult(nearest_event=nearest, est_days_before=round(smoothed, 1),
                        est_days_raw=round(est_raw, 1), band_days=round(band, 1),
                        confidence=round(conf, 3), regime_warnings=warnings)


# --------------------------------------------------------------------------- #
# Error-attribution loop — runs AFTER the fact to learn why an analog misled.
# --------------------------------------------------------------------------- #
@dataclass
class DivergenceLog:
    asof: dt.date
    predicted_event: str
    predicted_days_before: float
    realized_drawdown_30d: float      # what actually happened next month
    attribution: str                  # the explanation
    weight_adjustment: float          # multiplicative tweak applied to the analog's weight


def attribute_error(result: AnalogResult, realized_drawdown_30d: float,
                    crash_threshold: float = -0.10) -> DivergenceLog:
    """
    If the analog implied imminent danger (small days_before) but no drawdown materialized — or vice
    versa — record the miss and propose a weight adjustment + a human-readable reason.
    """
    implied_imminent = result.est_days_before < 45
    crashed = realized_drawdown_30d <= crash_threshold

    if implied_imminent and not crashed:
        reason = ("analog implied <45d to break but next-month drawdown was benign; "
                  "likely regime difference — " + ("; ".join(result.regime_warnings) or "unattributed"))
        adj = 0.85                                  # down-weight this analog
    elif not implied_imminent and crashed:
        reason = "break arrived earlier than the analog suggested; analog under-warned"
        adj = 1.10                                  # up-weight (it was conservative)
    else:
        reason = "analog directionally consistent with realized path"
        adj = 1.0

    return DivergenceLog(asof=dt.date.today(), predicted_event=result.nearest_event,
                         predicted_days_before=result.est_days_before,
                         realized_drawdown_30d=realized_drawdown_30d,
                         attribution=reason, weight_adjustment=adj)


# --------------------------------------------------------------------------- #
# Self-test (seed library is ILLUSTRATIVE — backfill real historical vectors in Phase 5)
# --------------------------------------------------------------------------- #
def _seed_library() -> list[AnalogDay]:
    rng = np.random.default_rng(1)
    lib = []
    # crude pattern: closer to peak => more stretched features (higher z on most axes)
    for event in ("cisco_2000", "gfc_2008", "top_2021"):
        for d in (180, 120, 90, 60, 45, 30, 15, 5):
            stretch = (180 - d) / 180.0
            base = np.array([+stretch, -0.5 * stretch, -stretch, +0.7 * stretch,
                             +stretch, +stretch, +0.4 * stretch, +stretch])
            lib.append(AnalogDay(event, d, base + rng.normal(0, 0.05, len(FEATURES))))
    return lib


if __name__ == "__main__":
    library = _seed_library()
    mu = {f: 0.0 for f in FEATURES}
    sd = {f: 1.0 for f in FEATURES}
    today = {"news_sentiment": 0.6, "put_call": -0.3, "pct_above_200dma": -0.55, "vix_level": 0.45,
             "margin_yoy": 0.7, "cohort_fwd_ps_z": 0.65, "capex_cut_signal": 0.3, "breadth_divergence": 0.7}
    recent = [110, 102, 98, 95, 92]               # prior raw daily estimates
    res = assess(today, mu, sd, library, recent,
                 regime_flags={"hyperscalers_cashrich": True, "etf_structural_bid": True})
    print(f"nearest analog : {res.nearest_event}")
    print(f"est days before: {res.est_days_before}  (raw {res.est_days_raw}, ±{res.band_days})")
    print(f"confidence     : {res.confidence}")
    for w in res.regime_warnings:
        print(f"  ! {w}")
    log = attribute_error(res, realized_drawdown_30d=-0.02)
    print(f"\nerror loop: {log.attribution}\n  weight adj -> {log.weight_adjustment}")
