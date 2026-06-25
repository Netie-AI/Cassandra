---
name: market-structure
description: >-
  Build or test the MARKET STRUCTURE subagent (StructureRead). Use for breadth
  metrics, OHLCV, index-breadth divergence, and phase.py inputs.
---

# Market Structure subagent

Prompt section: `agents/subagents.md` §2. Model: `claude-sonnet-4-6`. Returns: `StructureRead`.

## Mandate

Fetch index + basket OHLCV. Compute breadth:

- `pct_above_200dma`, `new_highs`, `new_lows`, `ad_line_slope`
- `index_breadth_divergence` (0–1) — index near highs while internals deteriorate

Save OHLCV CSV path for `phase.classify()`.

## Tools to wire

- `src/tools/polygon.py` (aggregates, grouped daily) or Alpha Vantage / Yahoo for v1

## Rules

- Compute divergence as normalized gap between index percentile-rank and breadth percentile-rank
- Pre-summarize in pandas; pass summaries to LLM, not raw rows
- Don't editorialize — phase classifier reads OHLCV

## Test in isolation

Standalone client pull → compute breadth metrics in code → return `StructureRead`.
