# DATA_SOURCES

Every API the system can use, what it provides, whether it's free, and which factor it feeds.

**Routing matrix (what to use when):** see **`docs/DATA_ROUTING.md`**  
**Env template:** `.env.example` · **Route config:** `config/data_sources.yaml`

Set keys in `.env`. `src/tools/<name>.py` reads them via `src/tools/_env.py` (loads `.env` automatically).

---

## Quick label legend

| Label | Meaning |
|-------|---------|
| **CORE** | Default provider for this job |
| **FALLBACK** | Use if CORE fails or rate-limited |
| **PAID** | Requires paid tier for full access |
| **OPTIONAL** | Scorer works without it (wider band) |
| **MANUAL** | Human research — not auto-ingested |
| **DEFERRED** | Documented, client not built yet |

---

## CORE stack (free-first — enough for Phase 2 MVP)

| Source | Provides | Feeds | ENV VAR | Label |
|--------|----------|-------|---------|-------|
| **yfinance** | US OHLCV, indices (^GSPC, ^VIX, ^SOX), basket prices | B, phase | none | **CORE** |
| **FRED** | Yields, spreads, liquidity, GDP/mcap | C, L, V | `FRED_API_KEY` | **CORE** |
| **FINRA** | Margin debt (monthly) | L | none | **CORE** |
| **Alpha Vantage** | OHLCV, news+sentiment | B, S, news | `ALPHAVANTAGE_API_KEY` | **CORE** (25 req/day) |
| **CoinGecko** | Crypto price, market cap, sentiment proxy | S | `COINGECKO_API_KEY` | **FALLBACK** crypto |

---

## Your configured paid / alt providers

| Source | Provides | Feeds | ENV VAR | Label |
|--------|----------|-------|---------|-------|
| **Massive / Polygon** | Options chains, aggregates, grouped breadth | B, S, options | `POLYGON_API_KEY` or `MASSIVE_API_KEY` | **CORE** options |
| **Marketstack** | Global EOD OHLCV | B | `MARKETSTACK_API_KEY` | **FALLBACK** |
| **EODHD** | EOD + fundamentals | B, V | `EODHD_API_KEY` | **FALLBACK** |
| **Finnhub** | Quotes, news, insiders | B, S, news, whale | `FINNHUB_API_KEY` | **FALLBACK** |
| **Twelve Data** | OHLCV alt | B | `TWELVEDATA_API_KEY` | **FALLBACK** |
| **Tavily** | Web search for news digestor | C, news | `TAVILY_API_KEY` | **CORE** web |
| **Unusual Whales** | Flow, dark pool, GEX | S, whale | `UW_API_KEY` | **PAID** optional |
| **FMP** | Insiders, 13F, transcripts | whale, V, C | `FMP_API_KEY` | **PAID** optional |
| **Tradier** | US quotes, options, paper trade | B, S, options | `TRADIER_API_TOKEN` | **OPTIONAL** |
| **Moomoo** | Asia HK/SG/MY/JP quotes + trade | B, Asia | OpenD local | **OPTIONAL** Asia |
| **Glassnode** | On-chain MVRV/NUPL | S | `GLASSNODE_API_KEY` | **OPTIONAL** |
| **ORATS** | Vol surface | S | `ORATS_TOKEN` | **OPTIONAL** |

---

## Python libraries (install separately — see DATA_ROUTING.md)

| Library | Use in CASSANDRA | Wired |
|---------|------------------|-------|
| [yfinance](https://github.com/ranaroussi/yfinance) | US OHLCV, indices | ✅ `yfinance_client.py` |
| [tessa](https://github.com/ymyke/tessa) | Unified Yahoo + CoinGecko | ⬜ optional wrapper |
| [bandl](https://github.com/stockalgo/bandl) | India NSE + crypto | ⬜ Asia/crypto alt |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Multi-provider + MCP | ⬜ optional aggregator |

---

## LLM providers

| Provider | Role | ENV VAR |
|----------|------|---------|
| OpenRouter | Multi-model gateway (recommended without Anthropic) | `OPENROUTER_API_KEY` |
| Groq | Fast inference fallback | `GROQ_API_KEY` |
| SEA-LION | SEA-localised optional | `SEA_LION_API_KEY` |
| Anthropic | Original BUILD spec | `ANTHROPIC_API_KEY` |

Set `llm.provider` in `config/data_sources.yaml`. Pre-summarize heavy payloads before LLM.

---

## Mapping cheat-sheet

- **Leverage loaded?** → FINRA + FRED  
- **Breadth diverging?** → yfinance → Polygon → Alpha Vantage  
- **Vol/positioning?** → Polygon options → Tradier → Unusual Whales  
- **Smart money distributing?** → FMP → Finnhub → UW  
- **Trigger pulling?** → FedWatch + news (AV/Finnhub/Tavily) + FRED liquidity  
- **Crypto confirmation?** → CoinGecko → Glassnode  

---

## Minimum viable key set (your setup)

```
FRED_API_KEY              (macro — CORE)
ALPHAVANTAGE_API_KEY      (news + OHLCV — CORE)
POLYGON_API_KEY           (Massive key — options/breadth)
COINGECKO_API_KEY         (crypto crossread)
TAVILY_API_KEY            (web search)
OPENROUTER_API_KEY        (LLM — or GROQ_API_KEY)
+ yfinance (no key) + FINRA scrape (no key)
```

Scorer down-weights missing inputs and widens confidence band — partial system stays honest.
