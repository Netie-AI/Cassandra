# HANDOFF → Next Cursor session

**Read this first.** Protocol: `.cursor/rules/600-protocol.mdc` · Full format: `docs/PROTOCOL.md`

## STOP — Phase 3 blocked

Claude issued **CONDITIONAL APPROVAL** (2026-06-25). Phase 2 ✅ approved. Phase 3 **blocked** until Claude reviews pipeline/store/api/cf_publish and sends APPROVED REVIEW_RESPONSE.

**Do not wire orchestrator LLM yet.**

---

## Deployment model (correct architecture)

```
Your laptop                    crash.netie.ai (Cloudflare Pages)
─────────────────              ────────────────────────────────
pipeline 3×/day                web/static/ dashboard (read-only)
  → scores.sqlite (local)        → fetch GET from KV Worker
  → publish_score() PUT          → renders CRS, band, phase
     to CF Worker → KV
```

Heavy work stays local. Cloudflare is publish-only. No SQLite on a server.

---

## Current state

| Item | Value |
|------|-------|
| Phase 2 | ✅ APPROVED (config + 1b clients) |
| Phase 3 | 🔒 BLOCKED — awaiting Claude code review |
| Publish | `src/tools/cf_publish.py` wired in `run_pipeline()` |
| Dashboard | `api/main.py` + `web/static/` — local dev; Pages for public |
| Next action | Push branch → Claude reviews on GitHub |

---

## Git hygiene (every session)

Before commit:

```bash
git status   # must NOT show: .env, *.sqlite, store/ohlcv/*.csv, others/, *.zip
```

- **Push to a branch** after any significant diff — Claude checks [GitHub](https://github.com/DietrichGebert/ponytail) online.
- `others/` = Claude drop archive only — **never commit** (gitignored).
- `store/` CSV/cache/sqlite = local runtime — **never commit**.

---

## If Claude APPROVES the 5 files

Then start Phase 3 only:

1. Wire `# WIRE:` in `src/orchestrator.py` (OpenRouter, no Anthropic)
2. `src/report.py` markdown renderer
3. Capex-cut grader ← `src/tools/tavily.py`
4. Cloudflare Worker (GET/PUT KV) + Pages deploy
5. Send REVIEW_REQUEST after `--run` produces DailyReport sections

---

## Mandatory Cursor message format

Every REVIEW_REQUEST / IMPLEMENT to Claude uses `docs/PROTOCOL.md` header (`═══ CASSANDRA ════`). Include VERIFY output you actually ran.

---

## Quick verify (any session)

```bash
python -m src.scoring      # CRS=56.9
python -m src.config       # Gate OK
python -m src.pipeline     # live CRS
uvicorn api.main:app --port 8080
```

## Ponytail rule

Read **this file + status.md + one phase spec**. Smallest diff. [ponytail](https://github.com/DietrichGebert/ponytail)

═══ END HANDOFF CURSOR ═══
