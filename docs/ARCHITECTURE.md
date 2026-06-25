# ARCHITECTURE

## Topology — orchestrator + 5 specialist subagents + 1 pure-math scorer

```
                          ┌─────────────────────────────┐
                          │   CASSANDRA ORCHESTRATOR     │
                          │   (claude-opus-4-8)          │
                          │   - owns the daily cycle     │
                          │   - dispatches subagents     │
                          │   - runs synthesis + writes  │
                          └──────────────┬──────────────┘
                                         │ dispatch (parallel)
        ┌────────────┬───────────────────┼───────────────────┬────────────┐
        ▼            ▼                   ▼                   ▼            ▼
 ┌────────────┐ ┌────────────┐  ┌────────────────┐ ┌──────────────┐ ┌──────────────┐
 │   NEWS     │ │  MARKET    │  │  DERIVATIVES   │ │    WHALE /   │ │ FUNDAMENTALS │
 │  DIGESTOR  │ │ STRUCTURE  │  │   & FLOW       │ │ SMART-MONEY  │ │  / FRAGILITY │
 │ (sonnet)   │ │ (sonnet)   │  │  (sonnet)      │ │ (sonnet)     │ │ (sonnet)     │
 └─────┬──────┘ └─────┬──────┘  └───────┬────────┘ └──────┬───────┘ └──────┬───────┘
       │              │                 │                 │                │
       │ NewsRead     │ StructureRead   │ FlowRead        │ WhaleRead      │ FragilityRead
       └──────────────┴────────┬────────┴─────────────────┴────────────────┘
                               ▼
                   ┌────────────────────────┐         ┌─────────────────────┐
                   │   QUANT SCORER          │◄────────│  PHASE CLASSIFIER   │
                   │   (pure code, no LLM)   │         │  (pure code)        │
                   │   scoring.py            │         │  phase.py           │
                   │   -> CRS, F, T, dF/dt   │         │  -> Wyckoff phase   │
                   └───────────┬─────────────┘         └─────────────────────┘
                               ▼
                   ┌────────────────────────┐
                   │   ORCHESTRATOR (pass 2) │
                   │   synthesis + report    │
                   │   report.py + LLM       │
                   └───────────┬─────────────┘
                               ▼
                   ┌────────────────────────┐
                   │  DailyReport (md) +     │
                   │  DailyScore -> store    │
                   └────────────────────────┘
```

**Why this split.** Each subagent owns one orthogonal evidence domain and one factor in the score.
Orthogonality matters: if News and Sentiment overlap, you double-count the same signal and the score
lies. The scorer is intentionally **pure code, not an LLM** — the number must be deterministic and
auditable. The LLM's job is research and narrative, never arithmetic.

---

## The DAG (maps cleanly onto Netie Cortex)

This is a textbook DAG and runs as-is on the Cortex runtime (Kahn topological order, the dead-code
eliminator prunes any source you don't subscribe to):

```
nodes:
  sources (leaves, parallel):   fred, finra, polygon, unusual_whales, fmp, news_api, glassnode?
  factor agents (depend on relevant sources):
        news_digestor      <- news_api, web_search_api
        market_structure   <- polygon (ohlcv/breadth)
        derivatives_flow   <- polygon (options), unusual_whales
        whale_smart_money  <- fmp (insider/13F), unusual_whales (darkpool), quiverquant
        fundamentals_frag  <- fred, finra, fmp
  scorer (depends on all 5 factor agents):  scoring.compute_crs
  phase  (depends on market_structure ohlcv): phase.classify   [parallel to scorer]
  report (depends on scorer + phase + all factor agents):  orchestrator pass-2
  persist (depends on report)
```

Execution: leaves run fully parallel; factor agents fan out; scorer + phase join; report reduces.
Same map/reduce shape as the by-hand process — many parallel pulls, one synthesis.

---

## Data flow per cycle

1. Orchestrator loads `settings.yaml` (basket, weights, windows, schedule).
2. Pulls **yesterday's** `DailyScore` from the store (needed for deltas + `dF/dt`).
3. Dispatches all 5 subagents in parallel. Each: calls its API tools → normalizes raw values into
   typed `MetricReading`s (with `asof`, `source`, `directionality`) → returns its `*Read` bundle.
4. Scorer consumes the 5 bundles → `compute_crs()` → `DailyScore` (CRS, F, T, per-factor breakdown,
   momentum, confidence band). Runs in parallel: `phase.classify()` on the OHLCV series.
5. Orchestrator pass-2 (Opus): takes the numeric `DailyScore` + phase + the raw evidence, writes the
   thesis — what changed, what's firing, who's next, **what would change its mind**, the timing caveat.
6. Persist `DailyScore` to timeseries store; write `report_YYYY-MM-DD.md`.

**Hard rule:** the LLM never computes the CRS. It receives the number and explains it. If a subagent's
data pull fails, it returns the metric as `None` with a reason; the scorer down-weights missing inputs
and *widens the confidence band* rather than guessing.

---

## Run schedule

Default: **07:30 local (Putrajaya, UTC+8)**, ≈ after the prior US close *and* the Asia session is
underway — so overnight tells (KOSPI/Taiwan memory, SK Hynix actions) are captured before you read.
A second optional run post-US-close (≈ 05:00 local) catches earnings reactions and capex-call NLP.

`start` button = `--run` (immediate cycle, ignores schedule).

---

## Storage

- `store/scores.sqlite` — `DailyScore` timeseries (the spine; powers `dF/dt`, deltas, charts).
- `store/evidence/YYYY-MM-DD/*.json` — raw subagent bundles (audit trail; lets you re-score history
  after a weight change without re-pulling APIs).
- `reports/report_YYYY-MM-DD.md` — the human deliverable.

Start with SQLite. Move to Postgres/Timescale only if you want multi-year minute data.

---

## Cost control

- Orchestrator reasoning (1–2 calls/day): `claude-opus-4-8`. Worth the quality on synthesis.
- Subagent fetch/extract/normalize (5 calls/day, high token volume from raw API payloads):
  `claude-sonnet-4-6`. Same family discipline, a fraction of the cost.
- Pre-filter API payloads in code *before* they hit the LLM (don't pay tokens to read a 50k-row
  options chain — compute put/call, skew, GEX in pandas, pass the LLM the summary).
- Paid data tiers are the real cost, not tokens. See `docs/DATA_SOURCES.md` for the free-first path; you can
  run a credible v1 on free sources (FRED + FINRA + Alpha Vantage) and add Polygon/Unusual Whales/
  Glassnode only where they earn their keep.
