# UI_SPEC (Phase 8)

Read-only, dark-first, instrument-grade dashboard. **No trade execution.**

## Stack

- Next.js + Tailwind + Recharts or visx
- Reads from `store/` (SQLite/Postgres) and `reports/`

## Panels

1. **CRS gauge** — score + confidence band (± halfwidth visible)
2. **Fragility vs trigger** — F and T side by side, interaction state
3. **Signal board** — firing / warning / watch from latest report
4. **Analog resemblance** — nearest event, days-before estimate, ±band, regime warnings
5. **Options shortlist** — ranked candidates + NO TRADE reasons when gated out
6. **History / compare** — today vs prior dates and historical crash windows

## Interaction rules

- **Every datum exposes source on hover** (`source`, `asof`, link)
- Buttons: "export thesis", "view sources" only — no "place trade"
- Uncertainty bands always visible where the backend provides them

## Data contract

- Primary: latest `DailyScore` + `DailyReport` markdown sections
- Secondary: `store/evidence/YYYY-MM-DD/*.json` for drill-down

## Acceptance gate

Dashboard renders a real `DailyReport`; hover shows attribution; read-only confirmed.
