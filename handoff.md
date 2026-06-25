# CASSANDRA — handoff.md

Protocol: `docs/PROTOCOL.md` · Cursor handoff: `HANDOFF_CURSOR.md` · Claude handoff: `HANDOFF_CLAUDE.md`

---

## To Claude — Phase 2 CONDITIONAL + 4-file review pending

**Date:** 2026-06-25  
**Claude verdict:** Phase 2 ✅ APPROVED · Phase 3 🔒 BLOCKED until 4-file code review

Claude must review: `src/pipeline.py`, `src/store.py`, `api/main.py`, `HANDOFF_CLAUDE.md`  
(Full file contents pasted in Cursor REVIEW_REQUEST message to user.)

### Cursor self-check (pre-review)

| File | Rule check |
|------|------------|
| pipeline.py | `scoring.compute_crs()` only — **no LLM** |
| pipeline.py | coverage passed to `compute_crs` → widens band |
| store.py | `metric_history` raw values + `daily_scores` F/T/band + `fragility_history()` |
| api/main.py | No trade/order endpoints; POST `/api/run` → `run_pipeline()` only |
| HANDOFF_CLAUDE.md | ≤1 page, phase + next action only |

---

## To Cursor — WAIT for Claude APPROVED on 4 files

Do **not** start Phase 3 until Claude REVIEW_RESPONSE says APPROVED.

### GATE STATUS

| Gate | Result |
|------|--------|
| ✅ Phase 0 regression | `python -m src.scoring` → CRS=56.9 |
| ✅ Phase 2 config | `python -m src.config` → weights loaded, CRS=56.9 with config |
| ✅ Phase 1b imports | yfinance, coingecko, finnhub, tavily import clean |
| ✅ yfinance live | pct_above_200dma=0.800 (8/10 above 200dma) |
| ⏳ coingecko live | MISSING (CoinGecko API blocked/empty in CI — key set in .env) |
| ✅ finnhub live | 20 articles, av_news_sentiment=0.485 |
| ✅ tavily live | capex_cut_search returns results (key set) |
| ✅ fmp key | FMP_API_KEY set — pipeline collects whale metrics |
| ✅ dashboard | `api/main.py` + `web/static/` — deploy docs/DEPLOY.md |
| ✅ pipeline | `python -m src.pipeline` → live CRS (coverage ~0.4 with partial data) |
| ✅ protocol | `.cursor/rules/600-protocol.mdc` installed |

### VERIFY output (machine)

```
python -m src.scoring
→ CRS=56.9  F=0.7052  T=0.6225  band=Mania  OK

python -m src.config
→ Loaded weights from settings.yaml
→ Worked example with config weights: CRS=56.9
→ Gate: OK CRS unchanged with config weights

python -m src.tools.yfinance_client
→ pct_above_200dma 0.800 | new_high_low -0.100 | divergence 0.000
→ Index OHLCV: store/ohlcv/^GSPC.csv

python -m src.tools.finnhub
→ 20 articles, av_news_sentiment=0.485

python -m src.pipeline
→ CRS=38.8 band=Awareness (live partial metrics — honest low coverage)
```

### Keys live

FRED, ALPHAVANTAGE, Massive/Polygon, FMP, Finnhub, Tavily, CoinGecko, Groq, OpenRouter — set. Tradier deferred. Alpaca optional (free paper).

### Also delivered this session

- `src/pipeline.py`, `src/store.py`, `src/tools/alpaca.py`
- Web app: `api/main.py`, `web/static/`, Docker, `docs/DEPLOY.md` for crash.netie.ai
- `HANDOFF_CURSOR.md`, `HANDOFF_CLAUDE.md` for clean session boundaries

### Questions

1. Approve Phase 2 ✅ and authorize Phase 3 (orchestrator LLM wiring via OpenRouter)?
2. coingecko MISSING in some environments OK if key works on deploy host?

---

## To Cursor — Phase 3 (pending Claude REVIEW_RESPONSE)

Wire orchestrator `# WIRE:` points. Capex-cut grader ← tavily. No Anthropic — use OpenRouter from `config/data_sources.yaml`.

---

## Completed handoffs

| Date | Type | Outcome |
|------|------|---------|
| 2026-06-25 | Claude→Cursor | Phase 2 IMPLEMENT (files3) |
| 2026-06-25 | Cursor→Claude | Phase 2 REVIEW_REQUEST + dashboard deploy scaffold |
