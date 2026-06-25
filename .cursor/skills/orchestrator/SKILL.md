---
name: orchestrator
description: >-
  Run the CASSANDRA orchestrator pass-2 synthesis on claude-opus-4-8. Use when
  wiring orchestrator.py, authoring DailyReport markdown, or synthesizing
  subagent evidence into the daily thesis.
---

# Orchestrator (claude-opus-4-8)

Full system prompt: `agents/orchestrator.md`. This skill encodes the wiring contract for Cursor.

## Role

Coordinate five specialist subagents, receive the deterministic `DailyScore` from `scoring.py`, and write an honest daily thesis. **You do NOT compute CRS.**

## Two passes

1. **Dispatch** — parallel subagent calls (sonnet). Collect typed `*Read` bundles.
2. **Synthesis** — feed `DailyScore` + phase + evidence + `agents/orchestrator.md` to opus. Output `DailyReport` sections.

## Required report sections

- Headline (CRS, band, dominant driver, F vs T lead)
- What changed vs yesterday
- Firing / Warning / Watch
- Who's next
- What would change my mind
- Timing caveat

## Hard boundaries

- Search before assert — no present-day facts from memory
- Fragility ≠ trigger — say "loaded, not fired" when appropriate
- No crash-date prediction, no Elliott Wave
- Decision-support only — never recommend specific trades or sizes

## Wiring

- `src/orchestrator.py` `# WIRE:` at pass-2
- Add `src/report.py` to render markdown from `DailyReport` schema
- Persist via `src/store.py` (SQLite)
