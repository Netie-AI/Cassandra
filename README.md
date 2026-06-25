# CASSANDRA

A daily multi-agent research system that detects where the AI/semiconductor market sits on the
mania → blow-off arc, and outputs a single auditable **Crash Risk Score (CRS)** plus a written thesis.

Named for the prophet who saw the fall and couldn't make anyone believe the *timing*. That is the
exact failure mode this system is built to fight: being structurally right and tactically early.

---

## What it is (and what it is NOT)

**It IS:** a decision-support tool. Every morning you press `start`. It runs the same research loop
we developed by hand — parallel domain research, quantitative scoring, honest synthesis — and hands
you one report. You read it, you decide.

**It is NOT:**
- An auto-trader. It places no orders, touches no broker, moves no money. It produces a *score and a
  report*. The trade decision is yours, every time. This boundary is load-bearing — do not remove it.
- A crystal ball. The CRS is a *fragility gauge with a trigger overlay*, not a proven predictor. It
  tells you how loaded the spring is and whether something is pulling the trigger. It does not tell
  you the day. Treat it as a structured opinion-former, not a signal to fire on blindly.
- Financial advice. It is a personal research instrument. Backtest it before you trust it with size.

---

## The one idea the whole system is built on

A crash needs **two** things, and they are different:

1. **Fragility (F)** — how loaded the system is: leverage, valuation, sentiment, deteriorating breadth.
   This is the *spring*. It builds slowly and can stay loaded for a long time.
2. **Trigger (T)** — active catalyst pressure: Fed tightening, supply-side cracks, capex cuts.
   This is the *spark*.

`CRS` is built as `f(F, T)` with an **interaction term**, so that high fragility with no trigger
reads "loaded but no spark" (elevated, not imminent), and high-both reads "danger zone." This is the
mathematical fix to the single most common bubble-call error: confusing a loaded spring for a fired one.

**Corollary that answers "does the risk decay if months pass with no crash?"** — No, not with calendar
time. The score decays only if **fragility itself is falling** (`dF/dt < 0`). If margin debt keeps
climbing and capex stays debt-funded, five quiet months mean the spring is *more* loaded, not less.
The system tracks `dF/dt` explicitly (see `src/scoring.py::fragility_momentum`).

---

## What we deliberately did NOT include

- **Elliott Wave counts.** Unfalsifiable and fit-to-taste. The source doc leaned on "fifth wave
  complete" — that is exactly the part that blows up early traders. Excluded on purpose.
- **Precise crash-date prediction.** The model outputs a *level + confidence band + phase*, never
  "it crashes on date X." Anything claiming the date is lying to you.

The honest signals we DO trust (mechanical, historically reliable): margin debt, breadth divergence,
vol term structure, supply-side tells, the capex/revenue gap, credit-spread complacency.

---

## Repo map

```
cassandra/
  README.md                 <- you are here
  BUILD.md                  <- sequential build plan (Cursor follows this)
  status.md                 <- current phase, gates, blockers
  handoff.md                <- Claude ↔ Cursor review (docs/PROTOCOL.md)
  requirements.txt
  .env.example
  config/
    settings.example.yaml   <- copy to settings.yaml
  docs/
    DATA_SOURCES.md         <- API map, env vars, labels
    DATA_ROUTING.md         <- what to use for what (priority matrix)
    NEWS_PIPELINE_SPEC.md
    SENTIMENT_ANALOG_SPEC.md
    OPTIONS_ENGINE_SPEC.md
    METHODS_REGISTRY.md
    UI_SPEC.md
    EVENT_MODULE_SPEC.md    <- Part 2 (deferred)
    PROTOCOL.md             <- Claude ↔ Cursor message format
  agents/
    orchestrator.md         <- Opus synthesis prompt
    subagents.md            <- 5 specialist prompts
  src/
    schemas.py              <- pydantic contracts
    scoring.py              <- CRS math (pure Python)
    phase.py                <- Wyckoff phase classifier
    orchestrator.py         <- daily cycle (wire LLM at # WIRE:)
    methods.py              <- pluggable method registry
    sentiment_analog.py     <- historical crash resemblance
    options_engine.py       <- gated options edge (NO TRADE default)
    calendar_guard.py       <- trading-day schedule
    tools/                  <- API clients (fred.py pattern)
  .cursor/
    rules/                  <- governance (.mdc, always-on + scoped)
    skills/                 <- per-role build skills (orchestrator, subagents, phase-builder, handoff)
    agents/                 <- Cursor agent role cards
  store/                    <- SQLite + evidence JSON
  reports/                  <- daily markdown output
  others/                   <- archived / superseded files
```

---

## Build order

See **`BUILD.md`** for the full phased plan (0–9 + Part 2). Cursor loads `.cursor/rules/` automatically.
Check **`status.md`** before starting; use **`handoff.md`** at each `[REVIEW]` gate.

Quick summary:

**Phase 0 — Scaffold.** `pip install -r requirements.txt`. Copy `config/settings.example.yaml` →
`config/settings.yaml` and `.env.example` → `.env`. Run self-tests (`python -m src.scoring`, etc.).

**Phase 1 — Data clients.** Implement `src/tools/*.py` free-first (FRED pattern exists).

**Phase 2 — Scoring.** Wire config weights; reproduce CRS worked example `[REVIEW]`.

**Phase 3 — Agents.** Wire `# WIRE:` in `orchestrator.py`; add `report.py` + `store.py`.

Phases 4–9: news pipeline, analog data, methods, options live wire, UI, deployment — see `BUILD.md`.

---

## Run

```bash
python -m src.orchestrator --run        # one full daily cycle now ("start")
python -m src.orchestrator --backtest   # replay over historical fixtures to calibrate weights
python -m src.orchestrator --schedule   # start the daily cron
```

Then send the generated report (and any weight changes) back for review — the scoring spec is
designed to be argued with.
