# CASSANDRA — status.md

**Updated:** 2026-06-26 (Phase 14 W22–W29 auth + deploy wiring)  
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
| 13 Auth / hardening | ✅ | W18–W21 complete; ops keys remain |
| 14 Ops command centre | ✅ | start.ps1, /ops, smoke, Supabase auth, GHA deploy |
| 15 Go-live | ✅ | privacy/ToS, email template, ops gate, subscribe overlay |
| 16 Resend sync | ✅ | audience contacts, batch send, smoke_live |

---

## UI deploy readiness (2026-06-25)

| Surface | Status | Notes |
|---------|--------|-------|
| Home dashboard | ✅ | styles.css restored; lang cycle; analog i18n |
| Newspaper | ✅ | Golden ZH/MS bodies in `newspaper-bodies.js` |
| Pricing | ✅ | I18N wired; lang cycle active |
| Docs (API / institutional / methodology) | ✅ | Shared v3 header |
| Stock desk (MU/NOW) | ✅ | Live quote via watchlist API |
| Agent chat on home | ✅ | Compact chat + trading engine tone; gate + max 320 tokens |
| Digest email signup | ✅ | Free list only — no paywall redirect |
| Contact | ✅ | `/api/contact` + diagnostic log email |
| Auth UI (login/signup) | ✅ | Stubs until Supabase keys |
| Rate limiting | ✅ | In-memory per-IP on `/api/*` |
| Error pages | ✅ | `404.html` + `500.html` |
| Smoke script | ✅ | `scripts/smoke_full.py` |
| Analog min-sim gate | ✅ | `MIN_SIM_THRESHOLD=0.82` in `src/analog.py` |
| Ops dashboard | ✅ | `/ops` + PIPELINE_KEY / localhost gated API |
| Launch script | ✅ | `scripts/start.ps1` uses `python -m uvicorn` |

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

See `docs/DEPLOY.md`. Local dev: `.\scripts\start.ps1` (or `python -m uvicorn api.main:app --port 8080`). CF Worker + Pages wiring ⏳ Phase 3.

---

## Blockers for go-live

1. Set payment URLs in `web/static/config.js`
2. Wire orchestrator end-to-end `--run` (Phase 5)
3. Supabase: add `SUPABASE_SERVICE_ROLE_KEY` + `SUPABASE_JWT_SECRET` to `.env` (URL set; auth STUB until both filled)
4. Live movers feed (demo OK for preview)
5. Restart API after deploy so smoke script hits current diagnostics shape

---

## Hard constraints

LLM never computes CRS · Fragility ≠ Trigger · No execution · Can say NO
