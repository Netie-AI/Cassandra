# CASSANDRA — operational plug-in guide
# Goal: open laptop at office → edition already generated → review → newsletter sends.

## Daily rhythm (your workflow)

| Time (local) | Action | Command / trigger |
|---|---|---|
| T−120 min | Auto pipeline starts | Windows Task Scheduler or `python -m src.orchestrator --schedule` |
| T−30 min | Review draft in browser | `http://localhost:8080/newspaper-report` |
| T (desk time) | Review dry-run, then live send | `python -m src.newsletter.send` then `--live` (see `docs/NEWSLETTER.md`) |
| After send | Publish score | `publish_score()` already runs inside `--run` when coverage ≥ gate |

Set `OPS_PRERUN_MINUTES=120` and `OPS_OFFICE_TIME=09:00` in `.env` (see `.env.example`).
Adjust `config/settings.yaml` `timezone` to match your desk.

## What to configure once

### 1. Supabase (accounts + watchlists + send log)

1. Create project at [supabase.com](https://supabase.com).
2. SQL Editor → paste `config/supabase.schema.sql` → Run.
3. Settings → API → copy URL + `service_role` key + JWT secret into `.env`:
   ```
   SUPABASE_URL=
   SUPABASE_ANON_KEY=
   SUPABASE_SERVICE_ROLE_KEY=
   SUPABASE_JWT_SECRET=
   ```
4. Auth → Email templates → customize confirm link → redirect to `/subscribe?confirmed=1`.
5. `pip install supabase pyjwt` when ready to switch off SQLite auth stub.

Local dev continues with SQLite + `X-Tier` header until Supabase env is set.

### 2. Email (newsletter)

**Recommended:** [Resend](https://resend.com) — one API key, good deliverability.

```
RESEND_API_KEY=
NEWSLETTER_FROM=Cassandra Desk <desk@crash.netie.ai>
NEWSLETTER_REPLY_TO=desk@netie.ai
```

**Alternative:** cPanel SMTP (same `.env` block):

```
SMTP_HOST=mail.yourdomain.com
SMTP_PORT=587
SMTP_USER=desk@yourdomain.com
SMTP_PASSWORD=
SMTP_TLS=true
```

Verify domain SPF/DKIM before first bulk send.

### 3. Data keys (pipeline)

Minimum for a honest daily run — see `.env.example` sections:
`FRED`, `ALPHAVANTAGE`, `FINNHUB`, `TAVILY`, `GEMINI`, `OPENROUTER`.

### 4. Scheduled runs

**Option A — always-on scheduler (laptop open):**
```powershell
python -m src.orchestrator --schedule
```
Fires 12:00 / 21:00 / 00:00 UTC+8 on NYSE trading days (`calendar_guard`).

**Option B — cron on the cloud VM (do not require Windows Task Scheduler):**
See `docs/NEWSLETTER.md`. Slots 0545 / 0600 / 1800 MYT map to UTC cron. Laptop xml stubs may stay on the laptop.

**Option B2 — Windows Task Scheduler (laptop only, optional):**
- Trigger: daily at your `OPS_OFFICE_TIME` minus 120 minutes
- Action: `python -m src.orchestrator --run`
- Start in: local Cassandra checkout
- Set `.env` loaded via system env or `setx`

**Option C — Cloudflare Worker cron** (post-deploy): see `docs/DEPLOY.md`.

### 5. Publish to crash.netie.ai

```
CF_KV_ENDPOINT=
CF_KV_SECRET=
PIPELINE_KEY=
```

Laptop runs pipeline → `publish_score()` → KV → Pages dashboard read-only.

## Storage map

| Data | Local (now) | Hosted (plug-in) |
|---|---|---|
| Scores + metrics | `store/scores.sqlite` | Keep local or replicate to Supabase `pipeline_runs` |
| Watchlists | SQLite `watchlists` table | Supabase `watchlists` when `SUPABASE_URL` set |
| User tier | `X-Tier` header stub | Supabase `profiles.tier` + JWT |
| Report bodies | SQLite `newspaper_bodies` | Same DB or Supabase blob table (future) |
| Send audit | — | Supabase `report_sends` |

## Checklist before first live newsletter

- [ ] `.env` filled (data + email + optional Supabase)
- [ ] `python -m src.orchestrator --run` exits 0 with coverage noted
- [ ] `/newspaper-report` shows today's edition in EN + ZH + MS toggle
- [ ] Test email: `python -c "from src.newsletter.send import send_edition; send_edition(to='you@…', subject='test', html='<p>ok</p>')"`
- [ ] Payment URLs in `web/static/config.js` (when Stripe links ready)
- [ ] Agent chat remains gated (`/agent` → Under Development)

## Not in this sprint

- Full Supabase JWT in `api/auth.py` (P9)
- Agent chat RAG endpoint (P10)
- Automated subscriber list sync from Stripe webhooks
