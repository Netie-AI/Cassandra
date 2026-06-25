---
name: fundamentals-fragility
description: >-
  Build or test the FUNDAMENTALS / FRAGILITY subagent (FragilityRead). Use for
  leverage, valuation, macro trigger inputs, and FINRA/FRED/FMP metrics.
---

# Fundamentals / Fragility subagent

Prompt section: `agents/subagents.md` §5. Model: `claude-sonnet-4-6`. Returns: `FragilityRead`.

## Mandate

Pull and compute L, V, and C macro inputs:

- `margin_debt_yoy`, `margin_to_mktcap`, `credit_spread`
- `cohort_fwd_ps`, `mktcap_to_gdp`, `top10_concentration`, `equity_risk_premium`
- `debt_funded_capex`, `fed_hike_odds`, `capex_rev_gap_slope`, `net_liquidity`

## Tools to wire

- `src/tools/finra.py` (margin debt CSV)
- `src/tools/fred.py` (spreads, yields, liquidity, GDP) — **pattern client exists**
- `src/tools/fmp.py` (fundamentals, cohort debt, transcripts)
- CME FedWatch (scrape or via Polygon)

## Rules

- Margin debt is monthly — flag lag for freshness penalty
- Spread tightness = complacency, not safety (invert at normalize)
- Capex/revenue gap slope is AI-specific fragility

## Test in isolation

`python -m src.tools.fred` for FRED subset → extend to full `FragilityRead`.
