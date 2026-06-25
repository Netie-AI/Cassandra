# CASSANDRA — status.md

**Updated:** 2026-06-25  
**Protocol:** `docs/PROTOCOL.md` · **Next Cursor:** `HANDOFF_CURSOR.md` · **Next Claude:** `HANDOFF_CLAUDE.md`

---

## Phase map

| Phase | Status | Gate |
|-------|--------|------|
| 4 UI + report | ✅ | Claude APPROVED 2026-06-25 |
| 5 Orchestrator | ✅ APPROVED spec | `# WIRE:` in `src/orchestrator.py` ⏳ |
| 5b LLM subagents | ✅ | `_llm.py` + OpenRouter extract wired |
| 5 capex grader | ✅ | `GRADER_SYSTEM` in `src/tools/capex_nlp.py` |
| 8 UI redesign | ✅ | Editorial home + newspaper + docs chrome |
| 9 Deploy | 🔄 | CF Worker + Pages |

---

## UI deploy readiness (2026-06-25)

| Surface | Status | Notes |
|---------|--------|-------|
| Home dashboard | ✅ | styles.css restored; lang cycle; analog i18n |
| Newspaper | ✅ | Golden ZH/MS bodies in `newspaper-bodies.js` |
| Pricing | ⏳ | English-only; lang button hidden until wired |
| Docs (API / institutional / methodology) | ✅ | Shared v3 header; no dead lang button |
| Stock desk (MU/NOW) | ✅ | Collapsible sidebar; live quote via watchlist API |
| Agent chat on home | ⏳ | Gate stub only; do not ungate for launch |

Reference docs for next agent window: `files4/DEBUG_REASONING_LOG.md`, `files4/GOLDEN_TRANSLATION_REFERENCE.md`, `files4/POLISH_FIXES.md`.

---

## Live clients (your machine)

| Client | Status |
|--------|--------|
| FRED | ✅ spreads |
| yfinance | ✅ 80% above 200dma |
| Alpha Vantage news | ✅ |
| Finnhub | ✅ 20 articles |
| Tavily | ✅ capex search works |
| FMP | ✅ key set |
| Pipeline | ✅ live CRS ~39 (partial coverage — honest) |
| CoinGecko | ⏳ verify on deploy host |
| Polygon options | ⏳ paid tier |

---

## Deploy crash.netie.ai

**Model:** laptop runs pipeline → `publish_score()` → Cloudflare KV → Pages dashboard (read-only).

See `docs/DEPLOY.md`. Local dev: `uvicorn api.main:app --port 8080`. CF Worker + Pages wiring ⏳ Phase 3.

---

## Blockers for go-live

1. Set payment URLs in `web/static/config.js`
2. Wire orchestrator end-to-end `--run` (Phase 5)
3. Supabase auth — see `PARKING_LOT.md`
4. Live movers feed (demo OK for preview)

---

## Hard constraints

LLM never computes CRS · Fragility ≠ Trigger · No execution · Can say NO
