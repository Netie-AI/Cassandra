"""
schemas.py — the data contract between subagents, the scorer, and the report.

Every subagent MUST return its bundle in these shapes. The scorer consumes only these types, never
raw API payloads. This is what keeps the LLM out of the arithmetic and makes the score auditable.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Atomic metric
# --------------------------------------------------------------------------- #
class Direction(int, Enum):
    BEARISH_HIGH = 1   # higher raw value => more bearish/fragile
    BULLISH_HIGH = -1  # higher raw value => more bullish (will be sign-flipped)


class MetricReading(BaseModel):
    """One observed metric, plus everything the scorer needs to normalize it."""
    name: str
    factor: str                         # one of: L, V, S, B, C
    raw_value: Optional[float]          # None if the pull failed
    direction: Direction
    source: str
    asof: datetime
    use_percentile: bool = False        # §2 non-normal override
    hard_threshold: Optional[float] = None   # documented extreme (e.g. MVRV-Z > 7)
    # Filled in by the normalizer (scoring.normalize); left None by the subagent:
    normalized: Optional[float] = Field(default=None, description="n_i in [0,1]")
    note: Optional[str] = None          # e.g. why a pull failed


# --------------------------------------------------------------------------- #
# Per-subagent bundles
# --------------------------------------------------------------------------- #
class NewsItem(BaseModel):
    headline: str
    summary: str                        # the agent's own words (no verbatim copying)
    url: str
    published: datetime
    signal_tag: str                     # e.g. "fed", "capex", "supply", "geopolitical"
    severity: float = Field(ge=0, le=1) # how bearish, 0..1
    affects_metric: Optional[str] = None  # which metric this news updates, if any


class NewsRead(BaseModel):
    items: list[NewsItem]
    # news can directly inform two trigger metrics via NLP:
    capex_cut_signal: float = Field(ge=0, le=1, description="0=no cut talk, 1=explicit guidance cut")
    supply_tell_signal: float = Field(ge=0, le=1, description="supply catching demand, 0..1")
    metrics: list[MetricReading] = []


class StructureRead(BaseModel):
    # raw series the phase classifier needs:
    ohlcv_csv_path: str                 # path to the OHLCV the agent fetched (for phase.py)
    pct_above_200dma: Optional[float]
    new_highs: Optional[int]
    new_lows: Optional[int]
    index_breadth_divergence: Optional[float]  # 0..1, index-high-while-internals-rot
    ad_line_slope: Optional[float]
    metrics: list[MetricReading] = []


class FlowRead(BaseModel):
    put_call_ratio: Optional[float]
    iv_skew_25d: Optional[float]        # 25Δ put - 25Δ call
    iv_term_structure: Optional[float]  # front - back (positive => backwardation => stress)
    gamma_exposure: Optional[float]     # dealer GEX
    retail_call_buying_streak: Optional[float]  # weeks net-buying / window
    metrics: list[MetricReading] = []


class WhaleRead(BaseModel):
    insider_sell_buy_ratio: Optional[float]
    inst_13f_net_flow: Optional[float]
    darkpool_short_volume_ratio: Optional[float]
    crypto_exchange_inflow: Optional[float] = None
    metrics: list[MetricReading] = []


class FragilityRead(BaseModel):
    margin_debt_yoy: Optional[float]
    margin_to_mktcap: Optional[float]
    credit_spread: Optional[float]
    cohort_fwd_ps: Optional[float]
    mktcap_to_gdp: Optional[float]
    top10_concentration: Optional[float]
    equity_risk_premium: Optional[float]
    debt_funded_capex: Optional[float]
    fed_hike_odds: Optional[float]
    capex_rev_gap_slope: Optional[float]
    net_liquidity: Optional[float]
    metrics: list[MetricReading] = []


# --------------------------------------------------------------------------- #
# Phase classifier output
# --------------------------------------------------------------------------- #
class Phase(str, Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    BUYING_CLIMAX = "buying_climax"
    AUTOMATIC_REACTION = "automatic_reaction"
    SECONDARY_TEST = "secondary_test"
    DISTRIBUTION_RANGE = "distribution_range"
    UPTHRUST_UTAD = "upthrust_utad"
    MARKDOWN = "markdown"
    UNDETERMINED = "undetermined"


class PhaseRead(BaseModel):
    phase: Phase
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]                 # the rules that matched


# --------------------------------------------------------------------------- #
# Final score + report
# --------------------------------------------------------------------------- #
class MomentumState(str, Enum):
    LOADING = "loading"
    PLATEAU = "plateau"
    BLEEDING = "bleeding"


class FactorBreakdown(BaseModel):
    L: float
    V: float
    S: float
    B: float
    C: float


class DailyScore(BaseModel):
    asof: date
    crs: float
    band_halfwidth: float
    confidence: float
    fragility: float
    trigger: float
    factors: FactorBreakdown
    momentum_state: MomentumState
    df_dt: float
    phase: Phase
    phase_confidence: float
    band_label: str                     # Benign / Awareness / Mania / Danger / Blow-off
    coverage: float                     # fraction of metrics present


class DailyReport(BaseModel):
    score: DailyScore
    headline: str
    what_changed: list[str]
    firing: list[str]
    warning: list[str]
    watch: list[str]
    whos_next: list[str]
    what_would_change_my_mind: list[str]
    timing_caveat: str
    markdown: str                       # the rendered report
