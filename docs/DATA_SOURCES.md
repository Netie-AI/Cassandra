# DATA_SOURCES

Every API the system can use, what it provides, whether it's free, and which factor it feeds. You said
you can create accounts — start with the **free** column; it's enough for a credible v1. Add paid
power-ups only where they earn their keep (flow, dark pool, on-chain).

Set keys in `.env` (names in the `ENV VAR` column). `src/tools/<name>.py` reads them.

---

## Free essentials (build these first — a real v1 runs on just these)

| Source | Provides | Feeds | ENV VAR | Notes / limits |
|---|---|---|---|---|
| **FRED** (St. Louis Fed) | Yields, real rates, credit spreads (BAA-10y, HY OAS), CPI, net liquidity inputs, market-cap/GDP components | C, L, V | `FRED_API_KEY` | Free, generous. The macro backbone. |
| **FINRA** | Margin debt + free credit balances (monthly) | L | none (CSV/scrape) | Monthly cadence → lags; handle freshness decay (§8). The single best leverage signal. |
| **Alpha Vantage** | Equity OHLCV, fundamentals, **news + sentiment** endpoint | B, V, S(news) | `ALPHAVANTAGE_API_KEY` | Free tier 25 req/day (tight) → cache aggressively or pay $50/mo for 75/min. |
| **CME FedWatch** | Implied rate-hike/cut probabilities | C (fed_path) | none (scrape) or via Polygon | The Fed-path trigger input. |
| **U.S. Treasury / Yahoo** | Index levels, ^VIX, sector ETFs | B, S | none | Free price data for breadth + vol level. |

---

## Paid power-ups (add in this priority order)

| Source | Provides | Feeds | ENV VAR | ~Cost | Why |
|---|---|---|---|---|---|
| **Polygon.io** | Real-time/historical equities **+ full options chains**, aggregates, some flow | B, S(IV/skew), structure | `POLYGON_API_KEY` | $29–199/mo | The workhorse once you outgrow free price/options. Compute GEX, skew, term structure from its chains. |
| **Unusual Whales** | **Options flow, dark-pool prints, gamma exposure, net premium** | S (flow), Whale | `UW_API_KEY` | ~$48/mo + API | The flow + dark-pool + GEX layer. Best single source for the Derivatives/Flow and Whale agents. |
| **Financial Modeling Prep (FMP)** | **Insider (Form 4), 13F institutional, fundamentals, earnings transcripts** | Whale, V, C(capex NLP) | `FMP_API_KEY` | $22–69/mo | Smart-money + the transcripts that feed the capex-cut NLP detector. |
| **QuiverQuant** | Congressional trades, insider clusters, alt-data sentiment | Whale, S | `QUIVER_API_KEY` | ~$10–50/mo | Cheap smart-money cross-read. |
| **Glassnode** | **BTC MVRV-Z, NUPL**, exchange flows, on-chain whale moves | S (crypto crossread) | `GLASSNODE_API_KEY` | $0 (limited)–$ | Only if `enable_crypto_crossread`. The behavioral analog metrics from the source thesis. |
| **ORATS** | Clean vol surface, term structure, skew (institutional grade) | S (vol regime) | `ORATS_TOKEN` | $$ | Optional upgrade over Polygon-derived vol if you want precision skew/term-structure. |

---

## LLM (the reasoning engine)

| Model | Role | ENV VAR |
|---|---|---|
| `claude-opus-4-8` | Orchestrator reasoning + daily synthesis (1–2 calls/day) | `ANTHROPIC_API_KEY` |
| `claude-sonnet-4-6` | Subagent fetch/extract/normalize (5 calls/day, high token volume) | same key |

Pre-summarize heavy payloads (options chains, transcripts) in pandas **before** the LLM sees them.

---

## Mapping cheat-sheet: which source answers which question

- "How loaded is leverage?" → FINRA (margin) + FRED (spreads) + FMP (cohort debt/capex).
- "Is breadth diverging?" → Polygon/Yahoo (% > 200dma, new highs−lows, A/D).
- "What's positioning/vol doing?" → Unusual Whales (flow, GEX) + Polygon/ORATS (skew, term structure).
- "Is smart money distributing?" → FMP (insiders, 13F) + Unusual Whales (dark pool) + Quiver.
- "Is a trigger pulling?" → CME FedWatch (Fed) + news/transcripts NLP (capex cuts, supply tells) + FRED (liquidity).
- "Crypto confirmation?" → Glassnode (MVRV-Z, NUPL) — optional.

---

## Minimum viable key set

To press `start` and get a real (if coarser) score on day one:
```
ANTHROPIC_API_KEY   (reasoning)
FRED_API_KEY        (macro/leverage/trigger)
ALPHAVANTAGE_API_KEY(price/news)
+ FINRA CSV (no key)  + FedWatch scrape (no key)
```
Then add Polygon → Unusual Whales → FMP in that order as budget allows. The scorer down-weights and
widens the confidence band for whatever you haven't wired yet, so a partial system is still honest —
just less sure of itself.
