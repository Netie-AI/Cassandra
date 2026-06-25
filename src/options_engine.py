"""
options_engine.py — turns a directional thesis (from the CRS / event view) into a RANKED, GATED
shortlist of OTM put/call candidates across three horizons. Decision-support only: it computes edge,
expected value, and the cost of being early. It NEVER places a trade and it is willing to say NO.

Core idea: the market prices a move via implied vol. Your thesis implies a *different* distribution —
specifically a fat left tail (the crash leg) that a plain lognormal misses. Edge exists only where
YOUR probability of finishing ITM exceeds the MARKET's. If it doesn't, the answer is NO TRADE.

Honesty features that are NOT optional:
  - Jump-diffusion thesis distribution (Merton-flavored) so the crash tail is modeled, not assumed away.
  - Theta-bleed accounting for the "bet every day until the event" pattern — it will tell you when the
    daily decay makes the position -EV before the catalyst can arrive.
  - A NO-TRADE gate on conviction, edge, EV-multiple, and confidence. Most days should return NO TRADE.

Run `python -m src.options_engine` for the self-test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

# --------------------------------------------------------------------------- #
# Horizons (DTE buckets). Mapped to the user's "near / long / far".
# --------------------------------------------------------------------------- #
class Horizon(str, Enum):
    NEAR = "near"     # ~this week (≈7 DTE)   high gamma+theta; only valid with a DATED catalyst
    MID = "mid"       # ~3 months (≈90 DTE)   balance
    FAR = "far"       # ~12 months (≈365 DTE) LEAPS; survives timing error — the structural-thesis horizon

HORIZON_DTE = {Horizon.NEAR: 7, Horizon.MID: 90, Horizon.FAR: 365}


# --------------------------------------------------------------------------- #
# Black-Scholes
# --------------------------------------------------------------------------- #
def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> float:
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if is_call else max(K - S, 0)
        return intrinsic
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if is_call:
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_greeks(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> dict:
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    pdf = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)
    delta = _norm_cdf(d1) if is_call else _norm_cdf(d1) - 1
    gamma = pdf / (S * sigma * math.sqrt(T))
    vega = S * pdf * math.sqrt(T) / 100
    # theta per CALENDAR DAY
    term1 = -(S * pdf * sigma) / (2 * math.sqrt(T))
    if is_call:
        theta = (term1 - r * K * math.exp(-r * T) * _norm_cdf(d2)) / 365
        prob_itm_rn = _norm_cdf(d2)
    else:
        theta = (term1 + r * K * math.exp(-r * T) * _norm_cdf(-d2)) / 365
        prob_itm_rn = _norm_cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta_per_day": theta,
            "prob_itm_riskneutral": prob_itm_rn}


def implied_move(S: float, sigma: float, T: float) -> float:
    """1-sigma move the market is pricing over horizon T (years)."""
    return S * sigma * math.sqrt(T)


# --------------------------------------------------------------------------- #
# Thesis distribution — jump-diffusion (the crash tail the whole thesis is about)
# --------------------------------------------------------------------------- #
@dataclass
class ThesisView:
    direction: str                 # "put" (bearish) or "call" (bullish)
    conviction: float              # 0..1  (from CRS confidence / event certainty)
    drift_annual: float            # expected diffusion drift of underlying under your view
    diffuse_vol_annual: float      # your diffusion vol (can differ from market IV)
    jump_prob_annual: float        # annualized probability of a jump (crash leg) occurring
    jump_mean: float               # mean jump size, e.g. -0.35 for a 35% down gap
    jump_sd: float = 0.10          # spread of the jump size


def simulate_terminal(S: float, T: float, view: ThesisView, n: int = 200_000,
                      seed: Optional[int] = 0) -> np.ndarray:
    """Monte-Carlo terminal prices under the thesis (diffusion + Poisson jump)."""
    rng = np.random.default_rng(seed)
    # diffusion leg (lognormal)
    z = rng.standard_normal(n)
    diff = (view.drift_annual - 0.5 * view.diffuse_vol_annual ** 2) * T \
        + view.diffuse_vol_annual * math.sqrt(T) * z
    log_ret = diff
    # jump leg: number of jumps ~ Poisson(lambda*T); each jump multiplies price
    lam = view.jump_prob_annual
    n_jumps = rng.poisson(lam * T, n)
    has = n_jumps > 0
    if has.any():
        jump_sizes = rng.normal(view.jump_mean, view.jump_sd, n) * np.minimum(n_jumps, 3)
        log_ret = log_ret + np.where(has, np.log1p(jump_sizes.clip(-0.95, 5.0)), 0.0)
    return S * np.exp(log_ret)


# --------------------------------------------------------------------------- #
# Per-candidate evaluation
# --------------------------------------------------------------------------- #
@dataclass
class OptionCandidate:
    ticker: str
    horizon: Horizon
    K: float
    is_call: bool
    market_premium: float          # from the chain (mid)
    iv: float                      # market implied vol
    S: float
    r: float = 0.045


@dataclass
class Evaluation:
    candidate: OptionCandidate
    market_prob_itm: float
    thesis_prob_itm: float
    edge: float                    # thesis_prob_itm - market_prob_itm
    ev_per_contract: float         # expected payoff - premium, under thesis distribution
    ev_multiple: float             # ev / premium
    theta_per_day_pct: float       # daily decay as % of premium
    breakeven_move_pct: float
    kelly_fraction: float
    verdict: str                   # "CANDIDATE" or "NO TRADE: <reason>"
    notes: list[str] = field(default_factory=list)


# Gate thresholds (tune in config). Defaults are deliberately strict — most days = NO TRADE.
GATES = {
    "min_conviction": 0.60,
    "min_edge": 0.08,              # your prob ITM must beat market's by ≥8 points
    "min_ev_multiple": 0.25,       # expected ≥ +25% on premium under your own distribution
    "near_requires_dated_catalyst": True,
}


def evaluate(c: OptionCandidate, view: ThesisView, terminal: np.ndarray,
             has_dated_catalyst_within_expiry: bool = False,
             gates: dict = GATES) -> Evaluation:
    greeks = bs_greeks(c.S, c.K, max(HORIZON_DTE[c.horizon] / 365, 1e-4), c.r, c.iv, c.is_call)
    market_prob = greeks["prob_itm_riskneutral"]

    payoff = np.maximum(terminal - c.K, 0) if c.is_call else np.maximum(c.K - terminal, 0)
    thesis_prob = float((payoff > 0).mean())
    exp_payoff = float(payoff.mean())
    ev = exp_payoff - c.market_premium
    ev_mult = ev / c.market_premium if c.market_premium > 0 else -1.0
    edge = thesis_prob - market_prob
    theta_pct = abs(greeks["theta_per_day"]) / c.market_premium if c.market_premium > 0 else 1.0
    breakeven = (c.K + c.market_premium - c.S) / c.S if c.is_call else (c.S - (c.K - c.market_premium)) / c.S

    # Kelly fraction f* = edge / net-odds, where net-odds ≈ (avg win / premium). Capped, never advice.
    avg_win = exp_payoff if exp_payoff > 0 else 0.0
    b = (avg_win / c.market_premium) if c.market_premium > 0 else 0.0
    kelly = max(0.0, min(0.25, (edge * (b + 1) - (1 - thesis_prob)) / b)) if b > 0 else 0.0

    notes: list[str] = []
    # --- NO-TRADE gate ---
    if view.conviction < gates["min_conviction"]:
        verdict = f"NO TRADE: conviction {view.conviction:.2f} < {gates['min_conviction']}"
    elif edge < gates["min_edge"]:
        verdict = f"NO TRADE: edge {edge:+.2f} < {gates['min_edge']} (market already prices your view)"
    elif ev_mult < gates["min_ev_multiple"]:
        verdict = f"NO TRADE: EV-multiple {ev_mult:+.2f} < {gates['min_ev_multiple']}"
    elif c.horizon == Horizon.NEAR and gates["near_requires_dated_catalyst"] and not has_dated_catalyst_within_expiry:
        verdict = "NO TRADE: near-dated needs a DATED catalyst inside the expiry (else theta bleed)"
    else:
        verdict = "CANDIDATE"

    # theta-bleed honesty for the "bet every day" pattern
    if theta_pct > 0.04:
        notes.append(f"theta bleed {theta_pct*100:.1f}%/day — daily re-buying compounds this fast")
    if c.horizon == Horizon.FAR:
        notes.append("LEAPS horizon survives timing error — the structural-thesis expression")

    return Evaluation(candidate=c, market_prob_itm=round(market_prob, 4),
                      thesis_prob_itm=round(thesis_prob, 4), edge=round(edge, 4),
                      ev_per_contract=round(ev, 4), ev_multiple=round(ev_mult, 3),
                      theta_per_day_pct=round(theta_pct, 4), breakeven_move_pct=round(breakeven, 4),
                      kelly_fraction=round(kelly, 4), verdict=verdict, notes=notes)


def rank_candidates(candidates: list[OptionCandidate], view: ThesisView,
                    has_dated_catalyst: dict[Horizon, bool] | None = None) -> list[Evaluation]:
    """Evaluate all, return PASS-the-gate first, ranked by EV-multiple."""
    has_dated_catalyst = has_dated_catalyst or {}
    evals = []
    for c in candidates:
        T = max(HORIZON_DTE[c.horizon] / 365, 1e-4)
        terminal = simulate_terminal(c.S, T, view)
        evals.append(evaluate(c, view, terminal,
                              has_dated_catalyst_within_expiry=has_dated_catalyst.get(c.horizon, False)))
    passed = [e for e in evals if e.verdict == "CANDIDATE"]
    failed = [e for e in evals if e.verdict != "CANDIDATE"]
    passed.sort(key=lambda e: e.ev_multiple, reverse=True)
    return passed + failed


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Bearish thesis with a real crash tail (the 2026 setup): modest down drift, fat left jump.
    view = ThesisView(direction="put", conviction=0.72, drift_annual=-0.05,
                      diffuse_vol_annual=0.45, jump_prob_annual=0.8, jump_mean=-0.35, jump_sd=0.12)
    S = 1000.0
    cands = [
        OptionCandidate("MU", Horizon.NEAR, K=900, is_call=False, market_premium=6.0, iv=0.55, S=S),
        OptionCandidate("MU", Horizon.MID,  K=800, is_call=False, market_premium=42.0, iv=0.50, S=S),
        OptionCandidate("MU", Horizon.FAR,  K=700, is_call=False, market_premium=85.0, iv=0.48, S=S),
    ]
    ranked = rank_candidates(cands, view, has_dated_catalyst={Horizon.NEAR: False})
    for e in ranked:
        c = e.candidate
        print(f"{c.ticker} {c.horizon.value:4s} {'P' if not c.is_call else 'C'}{int(c.K)} "
              f"prem={c.market_premium:>6} | mkt_pITM={e.market_prob_itm:.2f} thesis_pITM={e.thesis_prob_itm:.2f} "
              f"edge={e.edge:+.2f} EVx={e.ev_multiple:+.2f} theta/d={e.theta_per_day_pct*100:.1f}% -> {e.verdict}")
        for n in e.notes:
            print(f"      · {n}")
