# BUILD — the sequential execution plan for Cursor

This is the single document Cursor follows to build CASSANDRA end to end. Do the phases **in order**.
Each phase has an **acceptance gate** — do not advance until it passes. Phases marked **[REVIEW]**
produce an artifact to send back for verification before continuing.

The repo is already scaffolded (Part 1). This plan absorbs that scaffold and extends it with: a
pluggable methods layer, multi-region news + historical-crash sentiment analog, an options edge engine
with a hard NO-TRADE gate, a Palantir-grade UI, deployment, and a deferred Part 2 (event-driven
anticipatory catalyst module).

Governance: everything is bound by `.cursor/rules/*.mdc`. Read `.cursor/rules/000-project.mdc` first —
those ten rules override any instinct to cut a corner. The most important: the LLM never does
arithmetic; fragility ≠ trigger; no crash-date prediction; decision-support never execution; the
system can say NO.

**Claude ↔ Cursor gate:** read `status.md` before starting; update it after each gate. For `[REVIEW]`
phases, fill `handoff.md` and wait for Claude verification before advancing. Skills and subagent roles
live in `.cursor/skills/` and `.cursor/agents/`; specs live in `docs/`.

---

## Phase 0 — Scaffold + governance  ✅ (mostly done)

**Build:** confirm the tree, install deps, copy `config/settings.example.yaml` → `settings.yaml` and
`.env.example` → `.env`. Confirm `.cursor/rules/` is present so every subsequent edit is governed.

```bash
pip install -r requirements.txt
pip install exchange_calendars   # for accurate market-calendar awareness
```

**Acceptance gate:** `python -m src.scoring` prints `OK — reproduces CRASH_SCORE_SPEC §9` (CRS = 56.9).
`python -m src.phase`, `python -m src.options_engine`, `python -m src.sentiment_analog`,
`python -m src.calendar_guard`, `python -m src.methods` all run clean.

---

## Phase 1 — Data clients (free-first)

**Build:** implement `src/tools/*.py`, one source at a time, in this order: `fred.py` (done as the
pattern) → `finra.py` (margin debt CSV) → `alphavantage.py` (price + news) → then paid:
`polygon.py` (price/options/breadth) → `unusual_whales.py` (flow, dark pool, GEX) → `fmp.py`
(insiders, 13F, transcripts) → optional `glassnode.py` (MVRV/NUPL). Each returns typed
`MetricReading`s per `schemas.py`. See `docs/DATA_SOURCES.md` for the env vars and what each feeds.

**Acceptance gate:** each client, run standalone with a live key, prints real dated values. The
minimum viable set (Anthropic + FRED + Alpha Vantage + FINRA) is enough to proceed; the scorer
down-weights and widens the band for whatever isn't wired yet.

---

## Phase 2 — Scoring + phase  ✅ (implemented)

**Build:** nothing new — `scoring.py` and `phase.py` are done and tested. Wire `settings.yaml` weights
into them (load `intra_weights`, `factor_weights`, `crs_weights` instead of the module defaults).

**Acceptance gate [REVIEW]:** feed recorded fixtures through `compute_crs`; confirm the worked example
reproduces with config weights. **Send the reproduction back for review.** This is the math gate.

---

## Phase 3 — Agents (orchestrator + 5 subagents)

**Build:** implement the `# WIRE:` points in `src/orchestrator.py`. Each subagent = an
`claude-sonnet-4-6` call using its prompt from `agents/subagents.md` + its tool clients, returning
JSON parsed into the schema type. Orchestrator pass-2 = a `claude-opus-4-8` call using
`agents/orchestrator.md` to author the `DailyReport`. Add `src/report.py` to render the markdown.
Add `src/store.py` (SQLite): persist `DailyScore` timeseries + raw metric history + evidence JSON.

**Acceptance gate:** `python -m src.orchestrator --run` produces a full `DailyReport` markdown with all
required sections (headline, what-changed, firing/warning/watch, who's-next, what-would-change-my-mind,
timing-caveat) and persists a `DailyScore`. The LLM must NOT have touched the CRS number.

---

## Phase 4 — News pipeline upgrade (multi-region, translation, schedule)

**Build:** per `docs/NEWS_PIPELINE_SPEC.md`. Extend the News Digestor to:
- pull Korea (Naver/Daum finance) + China (Eastmoney/Sina/Caixin) sources for the basket, **via APIs
  where available, respecting robots.txt/ToS where scraping** (note network-allowlist constraints).
- translate non-English to English (LLM or DeepL) before analysis; keep original + translation + source.
- run **3× per trading day** through `calendar_guard.should_run()`: 12:00 (Asia settle), 21:00
  (pre-US-open prep), 00:00 (overnight). Skip non-trading days automatically.
- pull only the recent window (`calendar_guard.recent_window`).
- emit the two NLP trigger signals (`capex_cut_signal`, `supply_tell_signal`) carefully graded.

**Acceptance gate:** three scheduled runs fire only on trading days; non-English items show original +
translation + working source link; the capex-cut grader distinguishes a real guidance cut from hedging
on a labeled test set.

---

## Phase 5 — Historical-crash sentiment analog  ✅ (engine implemented)

**Build:** `sentiment_analog.py` is done. The remaining work is **data**: backfill real historical
feature vectors for the pre-crash windows (Cisco/dot-com 2000, GFC 2007–08, 2021 top — and the 2025
DeepSeek shock as a near-miss) into the analog library, replacing the seed. Wire today's feature
vector from the live subagent outputs. Persist the daily raw estimate so Gaussian smoothing has a
series. Wire `attribute_error` to run on a 30-day lag and adjust analog weights. See
`docs/SENTIMENT_ANALOG_SPEC.md` and **read its small-n warning** — this is a resemblance gauge, not a clock.

**Acceptance gate [REVIEW]:** the module reports a nearest analog, a smoothed days-before estimate with
a band, and regime warnings. **Send a week of outputs back for review** — we check the bands are
honest (wide) and the regime warnings fire.

---

## Phase 6 — Pluggable methods registry  ✅ (registry implemented)

**Build:** `methods.py` is done with three methods (`crs_v1`, `sentiment_analog`, `breadth_momentum`).
Wire their bodies against the real evidence bundles. Add config `method:` (single) or `ensemble:`
(list + weights). The orchestrator selects per config; ensemble disagreement lowers confidence and the
report says so. Add at least one more method per `docs/METHODS_REGISTRY.md` (e.g. a vol-regime method).

**Acceptance gate:** switching `method:` in config changes the score path; `ensemble:` reconciles
members and reports the score spread.

---

## Phase 7 — Options edge engine  ✅ (engine implemented) **[REVIEW]**

**Build:** `options_engine.py` is done and tested (the self-test shows a LEAPS passing and a weekly
OTM put correctly rejected for theta bleed). Remaining work:
- feed it the live thesis: map the day's `DailyScore`/method output → `ThesisView` (direction from the
  bearish/bullish read, conviction from confidence, `jump_*` from the crash-tail magnitude implied by
  the CRS band).
- pull the real option chains for the **top-10 semiconductor + top-10 tech names** (the most liquid,
  highest-valuation, cleanest OTM markets) for the three horizons (NEAR ≈7DTE, MID ≈90DTE, FAR
  ≈365DTE), build `OptionCandidate`s with live IV/premium.
- the **next-day learning loop**: store each ranked candidate; next session pull the realized option
  price + underlying move; compare predicted edge vs realized; log misses and feed an error report to
  the orchestrator ("our prediction was wrong because …"). This is the self-improvement the user asked
  for — keep the attribution honest (was it direction, timing, or vol that we mis-read?).

**Acceptance gate [REVIEW]:** on a Danger-band day the engine returns ranked FAR/MID candidates with
positive edge and a NO TRADE on the near-dated bleed; on a benign day it returns NO TRADE across the
board. **Send a few days of gated output + the next-day error reports back for review.** See
`docs/OPTIONS_ENGINE_SPEC.md` and `.cursor/rules/300-options-event-safety.mdc` — the gate is strict on
purpose, and there is no execution.

---

## Phase 8 — UI (Palantir-grade dashboard)

**Build:** per `docs/UI_SPEC.md`. A read-only, dark-first, instrument-grade dashboard (Next.js + Tailwind +
Recharts/visx). Panels: the CRS gauge with confidence band; fragility-vs-trigger split; the live
signal board (firing/warning/watch); the analog-resemblance panel with ±band and regime warnings; the
options shortlist with the NO-TRADE reasons shown; and a **history/compare view** putting today next to
prior dates and the historical-crash windows. **Every datum exposes its source on hover.** No
"place trade" button — "export thesis" and "view sources" only.

**Acceptance gate:** the dashboard renders a real `DailyReport`; hovering any number shows source +
asof + link; uncertainty bands are visible; it is read-only.

---

## Phase 9 — Deployment

**Build:** Dockerize. APScheduler (or a cron/worker) drives the 3× daily `calendar_guard`-gated runs.
Persist to a managed SQLite/Postgres. Host the UI (Vercel/Fly/Render); the worker runs the cycles and
writes reports the UI reads. Secrets via the host's env store. Add a healthcheck + a "last successful
run" indicator.

**Acceptance gate:** a clean deploy runs the daily cycle unattended on trading days and serves the
dashboard; a forced `--run` produces today's report end-to-end.

---

## Part 2 (deferred) — Event-driven anticipatory catalyst module

Build **after** Phase 9 is stable. Per `docs/EVENT_MODULE_SPEC.md`: a catalyst calendar +
thesis tracker that encodes second-order-beneficiary reasoning (the OpenAI-must-pick-AMD logic; the
Google-antitrust-Chrome window; "Buffett discloses → infer who → position"). It surfaces dated
catalysts and the anticipated beneficiary, then hands the options engine a `has_dated_catalyst=True`
for the relevant horizon so a near-dated position can pass the gate.

**Honesty requirement (non-negotiable):** the "bet every day until the event" pattern is a theta trap.
The module must model cumulative bleed (the engine already does) and tell you when the expected
catalyst window is too far for daily near-dated buying to be +EV — pushing you to a dated or
longer-horizon structure instead. It surfaces and gates anticipatory ideas; it never auto-fires them.

---

## How to drive this with Cursor

- Open the repo; `.cursor/rules/` load automatically and constrain every edit.
- Read `status.md` → work the current phase → update `status.md` when the gate passes.
- For each phase, prompt Cursor with the **Build** bullets and the named spec in `docs/`. Use a
  background/agent task per subagent (`.cursor/skills/<role>/`) and per tool client.
- After each **[REVIEW]** gate, fill `handoff.md` → Claude verifies → approve in `handoff.md` before
  continuing.
- Never skip a self-test or loosen a gate to "make it pass." A failing self-test means the math moved;
  a loosened gate means the system got dishonest. Both are stop-the-line events.
