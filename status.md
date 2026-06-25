# CASSANDRA — status.md

**Updated:** 2026-06-25  
**Protocol:** `docs/PROTOCOL.md` · **Next Cursor:** `HANDOFF_CURSOR.md` · **Next Claude:** `HANDOFF_CLAUDE.md`

---

## Phase 2 ✅ APPROVED · Phase 3 🔒 blocked (4-file review)

Claude CONDITIONAL: approve pipeline/store/api/handoff in code before Phase 3 LLM wiring.

| Phase | Status | Gate |
|-------|--------|------|
| 0 Scaffold | ✅ | CRS=56.9 self-tests |
| 1 Data clients | ✅ | All clients import; core live |
| 2 Config weights | ✅ awaiting Claude REVIEW | `python -m src.config` CRS=56.9 |
| 3 Agents | ⬜ | Full DailyReport via OpenRouter |
| 8 UI (early) | ✅ MVP | FastAPI + static dashboard |
| 9 Deploy | 🔄 scaffold | Docker + docs/DEPLOY.md → crash.netie.ai |

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

1. Claude REVIEW_RESPONSE on Phase 2
2. Wire orchestrator LLM via OpenRouter (no Anthropic)
3. Capex-cut grader ← tavily (critical calibration with Claude)

---

## Hard constraints

LLM never computes CRS · Fragility ≠ Trigger · No execution · Can say NO
