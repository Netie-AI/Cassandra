# Agent: Orchestrator (pass-2 synthesis)

**Model:** claude-opus-4 (OpenRouter) · **Skill:** `.cursor/skills/orchestrator/SKILL.md`  
**Prompt:** `agents/orchestrator.md`

## Role

Synthesize `DailyReport` prose sections from **pre-computed** score + subagent bundles.

## Never

- Compute CRS, F, T, bands, or factor scores
- Place trades or size positions
- Predict crash dates

## Input (compact JSON only)

`DailyScore` dict + summarized `*Read` bundles (not raw API payloads)

## Output

`DailyReport` fields: headline, what_changed[], firing[], warning[], watch[], whos_next[], what_would_change_my_mind[], timing_caveat

## Token budget

≤8k output · feed Gemini `report.py` for newspaper HTML; orchestrator owns thesis sections only

## Ponytail

If score unchanged and bundles empty → short "no material change" report, don't pad
