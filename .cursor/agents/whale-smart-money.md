# Agent: Whale / Smart Money

**Model:** claude-sonnet-4-6 · **Skill:** `.cursor/skills/whale-smart-money/SKILL.md`  
**Schema:** `WhaleRead` · **Spec:** `agents/subagents.md` §4

## Output contract

JSON `WhaleRead` only. Signal = **divergence** (insiders/institutions vs retail).

Metrics: insider sell/buy ratio, 13F net flow, dark pool ratio, optional crypto inflow

## Tools

`fmp`, `unusual_whales`, `coingecko` (optional)

## Never

Treat 13F as timing signal (lagged) · compute CRS · execution language

## On failure

Null metrics + note; 13F missing is common — flag in note
