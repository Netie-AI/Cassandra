# Cloudflare Worker — score publish + geo

Public read-only dashboard at **crash.netie.ai** fetches score JSON from this Worker. Your laptop publishes via `publish_score()` after each pipeline run.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/latest` | none | Latest score JSON from KV |
| GET | `/api/geo` | none | `{ "country": "MY" }` from `CF-IPCountry` |
| PUT | `/api/score` | `X-Secret` header | Laptop publish (matches `cf_publish.py`) |

## Setup

1. **KV namespace** — Cloudflare dashboard → Workers → KV → Create → copy namespace ID into `wrangler.toml`
2. **Worker** — deploy `cloudflare/worker.js` with binding `SCORE_KV`
3. **Secret** — Workers → Settings → Variables → `KV_SECRET` (same value as `.env` `CF_KV_SECRET`)
4. **Routes** — attach to `crash.netie.ai/api/*` or use Pages Functions proxy
5. **`.env` on laptop:**
   ```
   CF_KV_ENDPOINT=https://crash.netie.ai/api/score
   CF_KV_SECRET=<same as KV_SECRET>
   ```

## Pages routing

Static files from `web/static/` on Cloudflare Pages. Add `_redirects` or route rules:

```
/api/*  https://cassandra-score.<account>.workers.dev/api/:splat  200
```

Or colocate Worker as Pages Function.

## Payload shape (PUT body)

```json
{
  "crs": 38.8,
  "band": "Awareness",
  "fragility": 0.42,
  "trigger": 0.38,
  "phase": "distribution_range",
  "phase_confidence": 0.5,
  "coverage": 0.4,
  "asof": "2026-06-25"
}
```

GET `/api/latest` returns the same JSON. No raw metrics, no API keys.

## Local dev

FastAPI mirrors `/api/latest`, `/api/geo` (returns `US` or `X-Country` header). Dashboard falls back to `/api/dashboard` when KV is empty.

## Payment geo

Dashboard JS calls `/api/geo` → renders Billplz/Curlec (MY), Airwallex (CN), or Stripe/PayPal (default). Configure checkout URLs in `web/static/config.js`.
