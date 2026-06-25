---
name: whale-smart-money
description: >-
  Build or test the WHALE / SMART-MONEY subagent (WhaleRead). Use for insider
  ratios, 13F flows, dark pool, and optional on-chain whale signals.
---

# Whale / Smart-Money subagent

Prompt section: `agents/subagents.md` §4. Model: `claude-sonnet-4-6`. Returns: `WhaleRead`.

## Mandate

Compute:

- `insider_sell_buy_ratio` (Form 4)
- `inst_13f_net_flow`
- `darkpool_short_volume_ratio`
- Optional `crypto_exchange_inflow` (Glassnode)

Signal = **divergence** — insiders distributing into retail strength.

## Tools to wire

- `src/tools/fmp.py` (insiders, 13F)
- `src/tools/unusual_whales.py` (dark pool)
- Optional QuiverQuant, Glassnode

## Rules

- 13F is quarterly — weight for trend, not timing
- Pre-summarize heavy filings in pandas
- Feed "who's next" evidence to orchestrator pass-2

## Test in isolation

Pull insider + dark pool for basket leaders → return `WhaleRead`.
