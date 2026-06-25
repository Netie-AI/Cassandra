# Deploy CASSANDRA → crash.netie.ai

## Architecture

| Layer | Where | Role |
|-------|-------|------|
| Pipeline | Your laptop | FRED, FINRA, yfinance, scoring → `store/scores.sqlite` |
| Publish | Your laptop → Cloudflare Worker | `publish_score()` PUT after each run |
| Dashboard | Cloudflare Pages @ crash.netie.ai | Static `web/static/` fetches KV via Worker GET |

SQLite never leaves your machine. The public site is read-only.

## Quick start (local)

```bash
pip install -r requirements.txt
cp config/settings.example.yaml config/settings.yaml
cp .env.example .env   # fill keys
python -m src.pipeline   # first score
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080

## Publish to Cloudflare (Phase 3)

1. Create a Cloudflare Worker with KV binding + auth header `X-Secret`
2. Set in `.env`:
   ```
   CF_KV_ENDPOINT=https://your-worker.workers.dev/score
   CF_KV_SECRET=your-shared-secret
   ```
3. After each pipeline run, `publish_score()` PUTs JSON:
   `{crs, band, fragility, trigger, phase, phase_confidence, coverage, asof}`
4. Dashboard JS: `fetch()` Worker GET on page load

## Cloudflare Pages (crash.netie.ai)

1. Connect repo or upload `web/static/` to Pages
2. DNS (Spaceship): CNAME `crash` → `<project>.pages.dev`
3. Worker route: `/api/score` → KV read endpoint

## Docker (local dev only)

```bash
docker compose up -d --build
```

Mount `.env` and `store/` as volumes for local persistence.

## Alpaca (free paper data)

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Generate paper API keys
3. Set in `.env`:
   ```
   ALPACA_API_KEY=...
   ALPACA_SECRET_KEY=...
   ALPACA_PAPER=true
   ```
4. Test: `python -m src.tools.alpaca NVDA`

## Scheduled runs

APScheduler cron calling `python -m src.pipeline` 3× on trading days via `calendar_guard` (Asia PM / Pre-open / Overnight).
