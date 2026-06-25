# HANDOFF → Next Cursor session

**Read this first.** Protocol: `.cursor/rules/600-protocol.mdc` · Full format: `docs/PROTOCOL.md`

## Phase 3 — IN PROGRESS

Claude **APPROVED** Phase 2 deploy scaffold (2026-06-25). Orchestrator LLM wiring **unblocked**.

| Done this session | Next |
|-------------------|------|
| Palantir-grade dashboard (`web/static/`) | Wire `# WIRE:` orchestrator (OpenRouter) |
| Geo payment routing (MY/CN/intl) | Capex-cut grader ← tavily |
| Cloudflare Worker spec + `worker.js` | `src/report.py` DailyReport renderer |
| `/api/latest`, `/api/geo`, `PIPELINE_KEY` on `/api/run` | REVIEW_REQUEST with scoring.py |

---

## Deployment model

```
Laptop: pipeline 3×/day → scores.sqlite → publish_score() PUT → CF Worker KV
Pages:  web/static/ → GET /api/latest + /api/geo → render dashboard
```

Configure checkout URLs in `web/static/config.js`. Set `PIPELINE_KEY` before public launch.

---

## Git hygiene

```bash
git status   # no .env, *.sqlite, store/ohlcv, others/, *.zip
git push -u origin <branch>   # after every significant diff
```

---

## Quick verify

```bash
python -m src.scoring      # CRS=56.9
python -m src.pipeline     # live CRS
uvicorn api.main:app --port 8080   # open dashboard
```

═══ END HANDOFF CURSOR ═══
