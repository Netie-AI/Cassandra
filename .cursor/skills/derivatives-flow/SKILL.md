---
name: derivatives-flow
description: >-
  Build or test the DERIVATIVES & FLOW subagent (FlowRead). Use for put/call,
  IV skew, term structure, dealer gamma, and retail call streak signals.
---

# Derivatives & Flow subagent

Prompt section: `agents/subagents.md` §3. Model: `claude-sonnet-4-6`. Returns: `FlowRead`.

## Mandate

From options chain compute:

- `put_call_ratio`, `iv_skew_25d`, `iv_term_structure`
- `gamma_exposure` (dealer GEX)
- `retail_call_buying_streak`

## Tools to wire

- `src/tools/unusual_whales.py` (flow, GEX, net premium)
- `src/tools/polygon.py` (options chains)
- Optional ORATS for clean vol surface

## Rules

- Term-structure inversion (front IV > back) → surface loudly
- Compute everything in pandas from chain; never pass 50k-row chains to LLM
- Negative dealer gamma = move accelerant

## Test in isolation

Pull one liquid name chain → compute summaries → return `FlowRead`.
