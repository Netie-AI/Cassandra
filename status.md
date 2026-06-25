# CASSANDRA — status.md

**Updated:** 2026-06-25  
**Protocol:** `docs/PROTOCOL.md` · **Next Cursor:** `HANDOFF_CURSOR.md` · **Next Claude:** `HANDOFF_CLAUDE.md`

---

## Phase 4 ✅ APPROVED · Phase 5 orchestrator next

| Phase | Status | Gate |
|-------|--------|------|
| 4 UI + report | ✅ | Claude APPROVED 2026-06-25 |
| 5 Orchestrator | ⏳ | Wire `# WIRE:` orchestrator.py |
| 5 capex grader | ✅ scaffold | `src/tools/capex_nlp.py` |
| 8 UI v2 | ✅ | Mockup dashboard + Chart.js history |
| 9 Deploy | 🔄 | CF Worker + Pages |

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

## Blockers for Phase 5

1. Wire orchestrator `# WIRE:` (OpenRouter subagents + opus pass-2)
2. End-to-end `--run` produces DailyReport + publish
3. Set payment URLs in `web/static/config.js` before go-live
4. Supabase auth — PARKING_LOT.md

---

## Hard constraints

LLM never computes CRS · Fragility ≠ Trigger · No execution · Can say NO
