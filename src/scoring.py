"""
scoring.py — implements CRASH_SCORE_SPEC §1–§6 and §8. Pure functions, no LLM, deterministic.

The number must be reproducible and auditable. Run `python -m src.scoring` to execute the
worked-example self-test from CRASH_SCORE_SPEC §9 (asserts CRS == 56.7).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

# --------------------------------------------------------------------------- #
# Default weights (mirror CRASH_SCORE_SPEC §7; override from settings.yaml)
# --------------------------------------------------------------------------- #
INTRA = {
    "L": {"margin_yoy": .35, "margin_to_mktcap": .25, "credit_spread_inv": .20, "debt_capex": .20},
    "B": {"pct_above_200dma": .30, "new_high_low": .25, "divergence": .30, "ad_slope": .15},
    "V": {"cohort_fwd_ps": .35, "mktcap_gdp": .25, "top10_concentration": .20, "erp_inv": .20},
    "S": {"put_call_inv": .25, "retail_call_streak": .25, "iv_skew": .20, "survey": .15, "crypto_mvrv": .15},
    "C": {"fed_path": .30, "supply_tells": .25, "capex_cut_nlp": .25, "capex_rev_gap_slope": .10, "net_liquidity": .10},
}
FACTOR_W = {"L": .30, "B": .25, "V": .25, "S": .20}     # Fragility composition
CRS_W = {"a": .35, "b": .20, "c": .45}                  # F, T, interaction
K_STEEPNESS = 1.2
EPS_MOMENTUM = 0.005
MAX_BAND = 12.0
CONF_W = {"freshness": .35, "agreement": .40, "coverage": .25}

BANDS = [(25, "Benign"), (45, "Awareness"), (65, "Mania"), (80, "Danger"), (101, "Blow-off")]


# --------------------------------------------------------------------------- #
# §2 normalization
# --------------------------------------------------------------------------- #
def logistic(x: float, k: float = K_STEEPNESS) -> float:
    return 1.0 / (1.0 + math.exp(-k * x))


def normalize_zscore(raw: float, history: Sequence[float], direction: int, k: float = K_STEEPNESS) -> float:
    """Rolling z-score -> directional -> logistic squash to [0,1]."""
    h = np.asarray([v for v in history if v is not None], dtype=float)
    if h.size < 2:
        return 0.5
    mu, sigma = float(h.mean()), float(h.std(ddof=1))
    if sigma == 0:
        return 0.5
    z = (raw - mu) / sigma
    return logistic(direction * z, k)


def normalize_percentile(raw: float, history: Sequence[float], direction: int,
                         hard_threshold: Optional[float] = None) -> float:
    """Empirical percentile rank for non-normal metrics (§2 override)."""
    h = np.asarray([v for v in history if v is not None], dtype=float)
    if h.size < 2:
        return 0.5
    rank = float((h < raw).mean())          # fraction of history below raw
    n = rank if direction == 1 else (1.0 - rank)
    if hard_threshold is not None and ((direction == 1 and raw >= hard_threshold)
                                       or (direction == -1 and raw <= hard_threshold)):
        n = max(n, 0.9)
    return n


# --------------------------------------------------------------------------- #
# §3 factor aggregation (over PRESENT metrics only)
# --------------------------------------------------------------------------- #
def aggregate_factor(factor: str, normalized: dict[str, Optional[float]],
                     intra: dict | None = None) -> Optional[float]:
    """Weighted mean of present normalized metrics within one factor.
    `intra` overrides module-level INTRA defaults when supplied (from settings.yaml)."""
    w = (intra or {}).get(factor) or INTRA[factor]
    num = den = 0.0
    for name, weight in w.items():
        n = normalized.get(name)
        if n is None:
            continue
        num += weight * n
        den += weight
    return None if den == 0 else num / den


# --------------------------------------------------------------------------- #
# §4–§5 fragility, trigger, CRS
# --------------------------------------------------------------------------- #
@dataclass
class ScoreResult:
    crs: float
    fragility: float
    trigger: float
    factors: dict[str, float]           # L,V,S,B,C
    band: str
    band_halfwidth: float
    confidence: float
    coverage: float


def compute_fragility(L: float, V: float, S: float, B: float) -> float:
    w = FACTOR_W
    return w["L"] * L + w["V"] * V + w["S"] * S + w["B"] * B


def compute_crs_raw(F: float, T: float) -> float:
    a, b, c = CRS_W["a"], CRS_W["b"], CRS_W["c"]
    return a * F + b * T + c * (F * T)


def band_for(crs: float) -> str:
    for hi, label in BANDS:
        if crs < hi:
            return label
    return "Blow-off"


def fragility_momentum(f_history: Sequence[float], eps: float = EPS_MOMENTUM) -> tuple[float, str]:
    """OLS slope of recent Fragility (§6). Returns (slope, state)."""
    f = np.asarray([v for v in f_history if v is not None], dtype=float)
    if f.size < 3:
        return 0.0, "plateau"
    x = np.arange(f.size, dtype=float)
    slope = float(np.polyfit(x, f, 1)[0])
    if slope > eps:
        state = "loading"
    elif slope < -eps:
        state = "bleeding"
    else:
        state = "plateau"
    return slope, state


# --------------------------------------------------------------------------- #
# §8 confidence band
# --------------------------------------------------------------------------- #
def confidence_band(freshness: float, factor_scores: Sequence[float], coverage: float) -> tuple[float, float]:
    fs = np.asarray(factor_scores, dtype=float)
    agreement = 1.0 - float(fs.std(ddof=0)) / 0.5      # std normalized by max plausible spread 0.5
    agreement = max(0.0, min(1.0, agreement))
    conf = (CONF_W["freshness"] * freshness
            + CONF_W["agreement"] * agreement
            + CONF_W["coverage"] * coverage)
    conf = max(0.0, min(1.0, conf))
    band = (1.0 - conf) * MAX_BAND
    return conf, band


# --------------------------------------------------------------------------- #
# top-level entry
# --------------------------------------------------------------------------- #
def compute_crs(normalized_by_factor: dict[str, dict[str, Optional[float]]],
                freshness: float = 1.0,
                coverage: float = 1.0,
                weights: dict | None = None) -> ScoreResult:
    """
    normalized_by_factor: {"L": {metric: n_i}, ...} — n_i in [0,1] from §2, or None.
    weights: optional {'intra': {...}, 'factor': {...}, 'crs': {...}} from config.load_weights().
             If None, uses module-level defaults (INTRA, FACTOR_W, CRS_W) — backwards compatible.
    """
    _intra  = (weights or {}).get("intra")  or None   # None → aggregate_factor falls back to INTRA
    _fw     = (weights or {}).get("factor") or FACTOR_W
    _cw     = (weights or {}).get("crs")    or CRS_W

    factors: dict[str, float] = {}
    for f in ("L", "V", "S", "B", "C"):
        val = aggregate_factor(f, normalized_by_factor.get(f, {}), intra=_intra)
        factors[f] = 0.5 if val is None else val      # neutral fallback if whole factor missing

    # §4 — Fragility (F) and Trigger (T)
    F = (_fw.get("L", FACTOR_W["L"]) * factors["L"] +
         _fw.get("V", FACTOR_W["V"]) * factors["V"] +
         _fw.get("S", FACTOR_W["S"]) * factors["S"] +
         _fw.get("B", FACTOR_W["B"]) * factors["B"])
    T = factors["C"]

    # §5 — CRS with interaction term (the load-bearing formula: never remove c*F*T)
    a = _cw.get("a", CRS_W["a"])
    b = _cw.get("b", CRS_W["b"])
    c = _cw.get("c", CRS_W["c"])
    crs = 100.0 * (a * F + b * T + c * (F * T))

    conf, band = confidence_band(freshness, [factors[k] for k in ("L", "V", "S", "B", "C")], coverage)
    return ScoreResult(
        crs=round(crs, 1), fragility=round(F, 4), trigger=round(T, 4),
        factors={k: round(v, 4) for k, v in factors.items()},
        band=band_for(crs), band_halfwidth=round(band, 1),
        confidence=round(conf, 3), coverage=round(coverage, 3),
    )


# --------------------------------------------------------------------------- #
# Self-test: reproduce CRASH_SCORE_SPEC §9
# --------------------------------------------------------------------------- #
def _worked_example(weights: dict | None = None) -> ScoreResult:
    nbf = {
        "L": {"margin_yoy": .88, "margin_to_mktcap": .80, "credit_spread_inv": .75, "debt_capex": .70},
        "B": {"pct_above_200dma": .55, "new_high_low": .62, "divergence": .70, "ad_slope": .50},
        "V": {"cohort_fwd_ps": .78, "mktcap_gdp": .82, "top10_concentration": .85, "erp_inv": .72},
        "S": {"put_call_inv": .60, "retail_call_streak": .80, "iv_skew": .45, "survey": .55, "crypto_mvrv": .40},
        "C": {"fed_path": .90, "supply_tells": .65, "capex_cut_nlp": .30, "capex_rev_gap_slope": .60, "net_liquidity": .55},
    }
    return compute_crs(nbf, freshness=1.0, coverage=1.0, weights=weights)


if __name__ == "__main__":
    r = _worked_example()
    print(f"CRS={r.crs}  F={r.fragility}  T={r.trigger}  band={r.band}")
    print(f"factors={r.factors}  confidence={r.confidence}  band=±{r.band_halfwidth}")
    assert abs(r.crs - 56.9) < 0.1, f"spec mismatch: expected 56.9, got {r.crs}"
    assert r.band == "Mania"
    print("OK — reproduces CRASH_SCORE_SPEC §9")
