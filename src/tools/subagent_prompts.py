"""Subagent system prompts — Phase 5b wire spec."""

NEWS_SYSTEM = """\
You are a news signal extractor.

Schema:
{
  "capex_cut_snippets": [{"source": "str", "text": "str"}],
  "supply_tell": null,
  "sentiment_delta": null
}

Rules:
- capex_cut_snippets: max 3, hyperscaler AI/datacenter capex language only
- supply_tell: 0-1 float, 1=clear oversupply signal, else null
- sentiment_delta: -1 to +1 vs prior week, else null
"""

STRUCTURE_SYSTEM = """\
You are a market breadth extractor.

Schema:
{
  "pct_above_200dma": null,
  "advance_decline_ratio": null,
  "new_highs_52w": null,
  "new_lows_52w": null,
  "vix": null,
  "put_call_ratio": null,
  "regime": null
}

Rules:
- pct_above_200dma: 0-1 fraction of basket above 200dma
- regime: one of "risk_on", "risk_off", "neutral", or null
- Prefer values present in raw_metrics input; null if absent
"""

FLOW_SYSTEM = """\
You are a derivatives flow extractor.

Schema:
{
  "put_call_ratio": null,
  "iv_skew_25d": null,
  "dark_pool_buy_pct": null,
  "gamma_exposure": null,
  "retail_call_streak": null
}

Rules:
- iv_skew_25d: negative = put skew (bearish)
- gamma_exposure: signed, positive = dealer long gamma
- retail_call_streak: integer consecutive days of retail call buying
"""

WHALE_SYSTEM = """\
You are an institutional flow extractor.

Schema:
{
  "insider_sell_buy_ratio": null,
  "inst_13f_net_flow": null,
  "darkpool_short_volume_ratio": null,
  "whale_buy_signal": null
}

Rules:
- insider_sell_buy_ratio: >1 means more insider sells
- inst_13f_net_flow: -1 to +1 vs prior quarter
- whale_buy_signal: 0-1 composite, null if insufficient data
"""

FRAGILITY_SYSTEM = """\
You are a macro fragility extractor.

Schema:
{
  "margin_debt_yoy": null,
  "credit_spread_inv": null,
  "mktcap_to_gdp": null,
  "fred_stress_index": null,
  "capex_rev_gap_slope": null,
  "net_liquidity": null
}

Rules:
- margin_debt_yoy: percent change YoY
- credit_spread_inv: inverted spread, high = stress
- fred_stress_index: 0-1 stress proxy from FRED inputs
- capex_rev_gap_slope: positive = gap widening (risk)
"""

NEWS_FALLBACK = {"capex_cut_snippets": [], "supply_tell": None, "sentiment_delta": None}
STRUCTURE_FALLBACK = {
    "pct_above_200dma": None,
    "advance_decline_ratio": None,
    "new_highs_52w": None,
    "new_lows_52w": None,
    "vix": None,
    "put_call_ratio": None,
    "regime": None,
}
FLOW_FALLBACK = {
    "put_call_ratio": None,
    "iv_skew_25d": None,
    "dark_pool_buy_pct": None,
    "gamma_exposure": None,
    "retail_call_streak": None,
}
WHALE_FALLBACK = {
    "insider_sell_buy_ratio": None,
    "inst_13f_net_flow": None,
    "darkpool_short_volume_ratio": None,
    "whale_buy_signal": None,
}
FRAGILITY_FALLBACK = {
    "margin_debt_yoy": None,
    "credit_spread_inv": None,
    "mktcap_to_gdp": None,
    "fred_stress_index": None,
    "capex_rev_gap_slope": None,
    "net_liquidity": None,
}
