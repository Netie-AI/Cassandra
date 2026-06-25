# CASSANDRA — status.md

**Updated:** 2026-06-25  
**Protocol:** `docs/PROTOCOL.md` · **Next Cursor:** `HANDOFF_CURSOR.md` · **Next Claude:** `HANDOFF_CLAUDE.md`

---

## Phase 2 ✅ · Phase 3 dashboard ✅ · Phase 4 UI + report 🔄

| Phase | Status | Gate |
|-------|--------|------|
| 3 Dashboard | ✅ | Claude APPROVED 2026-06-25 |
| 4 UI + report | 🔄 | Newspaper, pricing, stocks, Gemini report.py |
| 4 Orchestrator | ⬜ | OpenRouter `# WIRE:` next |
| 8 UI | 🔄 | Main + newspaper + pricing |
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

## Blockers for Phase 3

1. Claude review scoring.py `confidence_band()` (coverage gate)
2. Wire orchestrator LLM via OpenRouter (no Anthropic)
3. Capex-cut grader ← tavily (critical calibration with Claude)
4. Set real payment URLs in `web/static/config.js` before go-live

---

## Hard constraints

LLM never computes CRS · Fragility ≠ Trigger · No execution · Can say NO
