# HANDOFF → Next Cursor session

**Read first:** `HANDOFF_CLAUDE.md` (orchestrator architecture + capex calibration) · `docs/PROMPT_ENGINEERING.md`

## Phase 5 — Orchestrator wiring (UNBLOCKED)

Claude APPROVED Phase 4 (2026-06-25). Wire `# WIRE:` in `src/orchestrator.py` on branch **`phase5-orchestrator`**.

### Do in order

1. **Calendar gate** — `calendar_guard.should_run()` before dispatch; skip if None
2. **5 subagents parallel** — `asyncio.gather(..., return_exceptions=True)`; failure → None
3. **Coverage** — `subagents_ok / 5` passed to `compute_crs`
4. **Normalize** — reuse `pipeline.normalize_metrics` pattern + `store.history_lookup`
5. **Score** — `scoring.compute_crs()` only; `phase.classify()` on OHLCV
6. **Report** — `report.generate_report_sections()` → Gemini (already wired)
7. **Persist** — `save_score` + `save_metrics` + `publish_score` (fail-safe)
8. **capex grader** — `src/tools/capex_nlp.py` + calibration from HANDOFF_CLAUDE.md

### LLM routing (`config/data_sources.yaml`)

- Subagents: OpenRouter `anthropic/claude-sonnet-4` (or Groq fallback)
- Orchestrator pass-2: OpenRouter `anthropic/claude-opus-4`
- Report text: `GEMINI_API_KEY` → `gemini-2.5-flash`
- capex_cut: `capex_nlp.score_capex_cut()` → Gemini first, OpenRouter fallback

### Ponytail rule

Smallest diff. Reuse `pipeline.py` + `store.py`. No duplicate math. JSON-only subagent outputs.

### After wiring — REVIEW_REQUEST to Claude

Paste `src/orchestrator.py` + gate output:
```bash
python -m src.orchestrator --run
python -m pytest tests/ -q
```

### UI (this session)

Dashboard upgraded from `cassandra_dashboard_ui_mockup.html` — centered CRS hero, factor bars, 30-day chart.

### Verify anytime

```bash
uvicorn api.main:app --port 8080
python -m pytest tests/test_scoring_band.py -q
```

**GitHub:** push `phase5-orchestrator` after significant diff.

═══ END HANDOFF CURSOR ═══
