# CASSANDRA build status

**Last updated:** 2026-06-24  
**Owner:** Cursor (implement) ↔ Claude (review) via `handoff.md`

---

## Current state

| Field | Value |
|-------|-------|
| **Current phase** | 1 — Data clients (free-first) |
| **Phase status** | Phase 0 gates passed; begin `finra.py` + `alphavantage.py` |
| **Last gate passed** | Phase 0 — all self-tests OK (2026-06-24) |
| **Next action** | Implement `src/tools/finra.py` and `src/tools/alphavantage.py`; run standalone with live keys |

---

## Phase checklist

| Phase | Name | Status | Gate |
|-------|------|--------|------|
| 0 | Scaffold + governance | ✅ gates passed | All `python -m src.*` self-tests |
| 1 | Data clients | ⬜ not started | Live key standalone prints |
| 2 | Scoring + config wire | ⬜ engine done, config wire pending | CRS reproduces `[REVIEW]` |
| 3 | Agents + store | ⬜ skeleton only | Full `--run` DailyReport |
| 4 | News pipeline | ⬜ not started | 3× schedule + translation |
| 5 | Sentiment analog data | ⬜ engine done, data pending | Week of outputs `[REVIEW]` |
| 6 | Methods registry | ⬜ registry done, wire pending | method/ensemble switch |
| 7 | Options live wire | ⬜ engine done, live wire pending | Gated output `[REVIEW]` |
| 8 | UI | ⬜ not started | Read-only dashboard |
| 9 | Deployment | ⬜ not started | Unattended trading-day runs |
| P2 | Event module | ⬜ deferred | Per `docs/EVENT_MODULE_SPEC.md` |

Legend: ✅ done · 🔄 in progress · ⬜ not started · 🔒 blocked on review

---

## Implemented (code exists)

- `src/scoring.py`, `src/phase.py`, `src/methods.py`, `src/sentiment_analog.py`, `src/options_engine.py`, `src/calendar_guard.py`
- `src/tools/fred.py` (pattern client)
- `src/orchestrator.py` (skeleton with `# WIRE:` markers)
- `agents/orchestrator.md`, `agents/subagents.md`
- `.cursor/rules/` (000–500), `.cursor/skills/` (7 skills), `.cursor/agents/` (6 roles)
- `docs/` specs (CRASH_SCORE, DATA_SOURCES, ARCHITECTURE, NEWS, SENTIMENT, OPTIONS, METHODS, UI, EVENT)

---

## Blockers

1. Remaining data clients not implemented (`finra`, `alphavantage`, `polygon`, etc.)
2. `src/report.py`, `src/store.py` not yet created (Phase 3)
3. Phase 2 config weight wiring not yet done

---

## Repo layout (post-reorg)

```
cassandra/
  BUILD.md              ← sequential plan (start here in Cursor)
  status.md             ← this file
  handoff.md            ← Claude ↔ Cursor gate artifacts
  README.md
  requirements.txt
  .env.example
  config/settings.example.yaml
  agents/               ← LLM system prompts
  docs/                 ← specs
  src/                  ← Python (scoring, agents, tools)
  .cursor/
    rules/              ← governance (.mdc)
    skills/             ← per-role build skills
    agents/             ← Cursor agent role cards
  store/                ← SQLite + evidence JSON
  reports/              ← daily markdown output
  others/               ← archived / superseded files
```

---

## Quick gate commands (Phase 0)

```bash
pip install -r requirements.txt
python -m src.scoring
python -m src.phase
python -m src.options_engine
python -m src.sentiment_analog
python -m src.calendar_guard
python -m src.methods
```
