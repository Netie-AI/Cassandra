---
name: phase-builder
description: >-
  Execute one BUILD.md phase with acceptance gates. Use when starting or
  completing a build phase, running self-tests, or preparing review artifacts.
---

# Phase builder

Read `BUILD.md` for the full sequence. Always check `status.md` first.

## Workflow per phase

1. Read the phase **Build** bullets and named spec in `docs/`
2. Load matching `.cursor/skills/<role>/SKILL.md` for isolated subagent/tool work
3. Implement only what the phase requires — no scope creep
4. Run acceptance gate commands (e.g. `python -m src.scoring`)
5. Update `status.md` with result
6. If gate is `[REVIEW]`, fill `handoff.md` artifact section for Claude review

## Phase quick-reference

| Phase | Focus | Gate |
|-------|-------|------|
| 0 | Scaffold + governance | All `python -m src.*` self-tests pass |
| 1 | Data clients | Each client prints real dated values |
| 2 | Scoring config wire | CRS reproduces with config weights `[REVIEW]` |
| 3 | Agents + store | Full `DailyReport` from `--run` |
| 4 | News pipeline | 3× schedule, translation, capex grader |
| 5 | Sentiment analog data | Week of outputs `[REVIEW]` |
| 6 | Methods registry | method/ensemble switch works |
| 7 | Options live wire | Gated output + error reports `[REVIEW]` |
| 8 | UI | Read-only dashboard with source hover |
| 9 | Deployment | Unattended trading-day cycles |

## Stop-the-line

- Failing self-test = math moved — fix before proceeding
- Loosened gate = dishonest system — do not ship
