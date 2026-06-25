# CASSANDRA Methodology

Auditable, source-traceable methods for every number shown to users.
No unfalsifiable claims. No crash-date predictions. LLMs narrate; Python computes.

See also: `docs/CRASH_SCORE_SPEC.md`, `src/scoring.py`, `src/phase.py`, `src/sentiment_analog.py`.

---

## 1. CRS (Crash Risk Score)

**Implementation:** `src/scoring.py` — pure Python, unit-tested against worked examples.

CRS is a weighted blend of normalized factor scores:

```
CRS = (a·F + b·T + c·F·T) mapped to 0–100 scale with confidence band ±halfwidth
```

Where:
- **F (Fragility)** = weighted mean of L, V, S, B factor aggregates
- **T (Trigger)** = catalyst factor aggregate (C)
- **Interaction term** `F·T` is load-bearing — never collapsed into a sum

### Premium "how we calculated this" panel shows per edition:

| Field | Source |
|-------|--------|
| Raw metric value | `metric_history` table, tagged `source` + `asof` |
| Normalization | z-score vs N-year baseline → logistic squash, or percentile rank |
| Weight | From `config/settings.yaml` (`intra_weights`, `factor_weights`, `crs_weights`) |
| Freshness | Timestamp per input; stale inputs widen band |
| Coverage | Fraction of expected inputs present live |

**Formula display (premium):**

```
CRS_display = Σ(normalized_i × weight_i) / Σ(weight_i) × 100
```

Only metrics with non-null normalized values contribute to denominator.

---

## 2. Wyckoff Phase

**Implementation:** `src/phase.py`

Documented Wyckoff schematics — not proprietary magic:

| Phase | Detection signals |
|-------|-------------------|
| Accumulation | Range compression, volume dry-up, spring patterns |
| Markup | Higher highs + expanding participation |
| Distribution | Lower highs on declining volume, failed breakouts (upthrust) |
| Markdown | Break of support on volume expansion |

**Output:** phase label + confidence (0–1) + 2–3 evidence strings.

Premium example:
> Distribution range, 55% confidence: lower highs on declining volume + failed breakout at resistance.

---

## 3. News Similarity Engine (2000-vs-today)

**Status:** Spec complete; embedding pipeline in progress.

### Pipeline

1. **Corpus** — Archive financial headlines + ledes for key windows (Mar 2000, Oct 2007, Feb 2020, …) with date, source, URL.
2. **Embed** — Today's news + corpus → same embedding model (e.g. text-embedding-3-small). Vectors cached; only new news re-embedded.
3. **Score** — Cosine similarity between today's vector(s) and each historical window.
4. **Surface** — Top-K matches with similarity (0–1), source, archived URL, date.

### Honesty guardrails

- Label: **"Descriptive, not predictive"**
- Show timing separation explicitly (±N days)
- Never imply "crash in X days"

Premium example:
> Today's Micron coverage scores 0.81 similarity to the 60-day window before the Mar 2000 peak. Closest match: WSJ "Chip demand seen insatiable" (0.89). [archive link]

---

## 4. Sentiment Extraction

**Pattern:** Same as `src/tools/capex_nlp.py` — structured JSON from LLM, scores computed in Python.

- Per-ticker and per-sector sentiment from news + earnings transcripts
- Score range: -1 to +1
- Compare to historical baselines (200-day, 1-year, 5-year where data exists)
- Show delta vs analog window

Example:
> AI-leader sentiment is +0.4, vs +0.7 at the Mar 2000 analog — euphoria cooling.

---

## 5. What We Do NOT Claim

| ❌ Forbidden | ✅ Instead |
|-------------|-----------|
| "Jane Street's leaked method" | Documented formulas + sources |
| "Predicts crashes" | Monitors fragility and trigger conditions |
| Specific crash dates / unfalsifiable probabilities | Analog + similarity + timing humility band |
| LLM-computed CRS | Python in `scoring.py` only |

---

## 6. Token Efficiency

- Pre-summarize raw data in Python before any LLM call
- JSON-only extraction outputs with deterministic parsing guards
- System prompt holds rubric once — no duplication per call
- Cache embeddings; batch subagent calls via `asyncio.gather`

---

## 7. Daily Generation

**Schedule:** 3× daily on trading days (04:00 / 13:00 / 16:00 UTC).

Each run produces **one edition** shared by all readers:
- Free: morning edition + 2-day score delay
- Paid: all three editions + live score

**Personalization:** Homepage watchlist is the only per-user element (paid tier).

### Report depth by tier

| Tier | Content |
|------|---------|
| Free | Front-page narrative, headline, direction, sentiment |
| Report+ | CRS breakdown, Wyckoff evidence, news-similarity comparables with sources, sentiment deltas, per-ticker fragility, analog map (~5 pages) |

---

## 8. Agent Chat Gate

**Implementation:** `src/tools/agent_gate.py`

Pre-LLM fuzzy keyword filter:
- `score_message(text)` → relevance 0–1
- Blocked patterns: prompt injection, API key requests, instruction leaks
- If score < 0.4 → canned response, no LLM invocation
- Blocked attempts logged to `agent_gate_log` for future classifier training

---

*Last updated: 2026-06-25 · Cassandra Research Desk*
