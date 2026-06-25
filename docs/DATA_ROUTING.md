# DATA_ROUTING.md — what to use for what, by subagent, by metric

## Routing priority: CORE → FALLBACK → PAID
Use CORE first. If it fails, try FALLBACK. Add PAID only when CORE/FALLBACK can't give the metric.

---

## By subagent

### Market Structure (factor B — breadth)
| Metric | CORE | FALLBACK | Notes |
|---|---|---|---|
| pct_above_200dma | yfinance_client.py | polygon.py | yfinance free, no key |
| new_high_low | yfinance_client.py | polygon.py (grouped daily) | |
| index_breadth_divergence | yfinance_client.py | manual | computed from above two |
| OHLCV CSV for phase.py | yfinance_client.py | polygon.py | yfinance saves to store/ohlcv/ |

### Fundamentals / Fragility (factors L, V, C)
| Metric | CORE | FALLBACK |
|---|---|---|
| margin_debt_yoy, margin_to_mktcap | finra.py | FRED (indirect) |
| credit_spread_inv, net_liquidity | fred.py | — |
| mktcap_gdp | fred.py (WILL5000+GDP) | — |
| cohort_fwd_ps, top10_concentration | fmp.py | alphavantage.py fundamentals |
| debt_funded_capex | fmp.py cash-flow | manual (EDGAR) |
| fed_hike_odds | CME FedWatch scrape | fred.py (DFII10 proxy) |
| capex_rev_gap_slope | fmp.py CF+income | manual |

### News Digestor (factors C — trigger signals + S — sentiment)
| Signal | CORE | FALLBACK | Source type |
|---|---|---|---|
| capex_cut_signal (0→1) | tavily.py → alphavantage.py NLP | finnhub.py NLP | Primary source text → LLM grader |
| supply_tell_signal (0→1) | tavily.py → alphavantage.py | finnhub.py | Trade press |
| av_news_sentiment | alphavantage.py | finnhub.py | Same schema name, swappable |
| Asia session news | tavily.py (asia_semiconductor_news) | Moomoo (Phase 4) | English translations |

### Derivatives & Flow (factor S)
| Metric | CORE | FALLBACK | Notes |
|---|---|---|---|
| put_call_inv | polygon.py | unusual_whales.py | Polygon needs paid for full chain |
| iv_skew, iv_term_structure | polygon.py | unusual_whales.py | |
| gamma_exposure | unusual_whales.py | polygon.py | UW GEX more accurate |
| retail_call_streak | unusual_whales.py | manual | UW market/summary endpoint |

### Whale / Smart Money (factor S + report)
| Signal | CORE | FALLBACK |
|---|---|---|
| insider_sell_buy_ratio | fmp.py (Form 4) | quiverquant.py (Phase 6) |
| inst_13f_net_flow | fmp.py (13F) | manual |
| darkpool_short_ratio | unusual_whales.py | — |
| crypto_exchange_inflow | coingecko.py (proxy) | glassnode.py (Phase 6) |

### Crypto Crossread (factor S — optional, weight 0.15)
| Metric | CORE | FALLBACK | Notes |
|---|---|---|---|
| crypto_mvrv | coingecko.py (200dma proxy) | glassnode.py (true MVRV) | Proxy is approximate |
| crypto_nupl | coingecko.py (proxy) | glassnode.py (true NUPL) | |
| survey (Fear & Greed) | alternative.me (via coingecko.py) | — | Free, no key |

---

## By data type

| Data type | Source | Key | Tier |
|---|---|---|---|
| US OHLCV + breadth | yfinance_client.py | none | FREE |
| Macro (rates, spreads, liquidity) | fred.py | FRED_API_KEY | FREE |
| Margin debt | finra.py | none | FREE (CSV) |
| News + sentiment | alphavantage.py / finnhub.py | AV / Finnhub key | FREE |
| Web research / primary sources | tavily.py | TAVILY_API_KEY | FREE tier |
| Crypto sentiment proxy | coingecko.py | optional demo key | FREE |
| Options chain, breadth (paid) | polygon.py | POLYGON_API_KEY | $29+/mo |
| Flow, dark pool, GEX | unusual_whales.py | UW_API_KEY | $48+/mo |
| Insiders, 13F, transcripts | fmp.py | FMP_API_KEY | $22+/mo |
| Asia market data | moomoo (Phase 4) | OpenD local | Moomoo account |

---

## MANUAL ONLY (research context, not auto-ingested)

Statista, Trading Economics, World Bank, BLS, Crunchbase, Koyfin, EDGAR, ABI Research, IDC,
Gartner, FactSet, ValueInvestorsClub, SeekingAlpha — listed in docs/DATA_SOURCES.md for human
research context. The News Digestor can reference these via tavily.py search but they are not
wired into the MetricReading pipeline.

---

## Regional / specialty (deferred)

| Source | Use | Phase |
|---|---|---|
| Tradier | US options + paper trading | Phase 7 (options execution sandbox) |
| Moomoo (py-moomoo-api) | Asia HK/SG/MY/JP real-time data | Phase 4 |
| bandl | India NSE (not in US semis basket) | Phase 4 if basket expands |
| OpenBB | Multi-provider aggregator | Optional (heavy dependency) |
| yfinance via tessa | Lighter OpenBB alternative | Phase 6 if yfinance fails |
