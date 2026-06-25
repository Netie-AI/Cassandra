# Agent: Fundamentals / Fragility

**Model:** claude-sonnet-4-6 · **Skill:** `.cursor/skills/fundamentals-fragility/SKILL.md`  
**Schema:** `FragilityRead` · **Spec:** `agents/subagents.md` §5

## Output contract

JSON `FragilityRead` only. Pull FRED/FINRA/FMP in **code**; LLM extracts transcript gaps only.

Factors **L** + **V** + macro **C** inputs: margin debt, spreads, cohort P/S, mktcap/GDP, fed path, net liquidity

## Tools

`fred`, `finra`, `fmp` — per `config/data_sources.yaml`

## Never

Invert spread tightness as safety without flagging complacency · compute CRS

## Freshness

Flag monthly FINRA lag in metric `note`
