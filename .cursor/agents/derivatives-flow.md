# Agent: Derivatives & Flow

**Model:** claude-sonnet-4-6 · **Skill:** `.cursor/skills/derivatives-flow/SKILL.md`  
**Schema:** `FlowRead` · **Spec:** `agents/subagents.md` §3

## Output contract

JSON `FlowRead` only. Pre-aggregate options chain in pandas before any LLM sees it.

Metrics → factor **S**: `put_call_inv`, `iv_skew`, `retail_call_streak`, dealer gamma proxy

## Tools

`unusual_whales`, `polygon` (optional paid)

## Red flags to surface in `notes[]`

Backwardation · steepening skew · short dealer gamma · retail call streak

## Never

Pass raw chain rows to LLM · compute CRS · recommend trades
