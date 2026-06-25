# CASSANDRA — PARKING LOT
> Features agreed but NOT in current sprint. Review before each new Phase.
> Last updated: 2026-06-25

---

## 🔒 Auth + Subscriptions (Phase 4)

### Supabase auth flow
- Sign-up: email + password → hash via Supabase → send confirmation email
- Confirm link → auto-login → redirect to `/dashboard?tier=free`
- Upgrade flow: pay → Stripe/Billplz/Airwallex webhook → update `user_tier` in Supabase
- `user_tier` values: `free | report | briefing | agent`
- Session: JWT stored in localStorage; refreshed on each visit
- Forgot password: Supabase magic link

### Email confirmation UX
- After form submit → "Check your email" screen (no redirect yet)
- Confirmation link → POST `/api/confirm?token=xxx` → activate account → redirect to dashboard
- Resend button after 60s

### Supabase schema (design first, build later)
```sql
users (id, email_hash, tier, created_at, confirmed_at)
subscriptions (id, user_id, stripe_sub_id, billplz_ref, status, renews_at)
report_sends (id, user_id, report_date, sent_at, opened_at)
```

---

## 📰 Report generation (Phase 4)

### Gemini Flash report writer
- Model: `gemini-2.5-flash` (free tier, 10 RPM — sufficient for 3 runs/day)
- API key: get from ai.google.dev → AI Studio → Create API key → add to .env as `GEMINI_API_KEY`
- Input: structured JSON from `run_pipeline()` output
- Output: newspaper-style markdown for each tier

### Tier report lengths
| Tier | Format | Pages | Generated once/day | Distribute to all |
|---|---|---|---|---|
| Free (email) | 1-page plain text | 1 | ✅ | ✅ all free |
| $4.99 Report | newspaper-report.html | 5 | ✅ | ✅ all $4.99 |
| $10 Briefing | newspaper-report.html × 2 + AI insights | 10 | ✅ | ✅ all $10 |
| $50 Agent | 10 pages + custom stock pages | 10 + custom | ⚠️ per-user custom | per user |

### Image generation for reports
- Model: `gemini-2.5-flash-image` (free, 500/day) → migrate to `gemini-3.1-flash-image-preview` before Oct 2026
- Use case: 1 chart/chart-like illustration per report (historical analog visual, zone chart)
- Keep to 1 image/report to stay well within free quota

### Historical analog comparison data
- Need: real historical CRS-equivalent values for 1999-2000, 2007-2008, 2021-2022
- Source: reconstruct from FRED/FINRA archival data (big data work — Phase 5+)
- Placeholder: hardcoded seed data in newspaper-report.html for demo

---

## 💎 Tier system (Phase 4–5)

### Tier 0 — Free
- Dashboard: CRS + band + L + V factors + phase + countdown
- Email: 1-page daily summary (plain text, score + band + next update)
- Newspaper page: read-only, S/B/C locked

### Tier 1 — $4.99/month "The Report"
- All Free features
- 5-page newspaper-style daily email report
- All 5 factors (L, V, S, B, C) unlocked
- capex NLP signal detail
- Historical analog comparison (nearest date + 3 metrics)
- Payment: Stripe (intl) / Billplz or Curlec (MY) / Airwallex (CN)

### Tier 2 — $10/month "The Briefing"
- All Report features
- 10-page report + dedicated AI insights section
- Side-by-side historical comparison with identified analog
- All metrics with source attribution + freshness indicator
- Generated once/day, same content for all Tier 2 users

### Tier 3 — $50/month "The Agent"
- All Briefing features
- Custom stock watchlist (up to 10 tickers)
- Stock-specific crash score per ticker (dedicated CRS per stock)
- Custom daily email with your stocks
- API access: JSON endpoint `/api/v1/stocks/{ticker}/score` with API key
- Chat with CASSANDRA (Gemini Flash, capped 50 messages/day)
- Add-on API credits: $5 = 500 extra API calls

### Tier pricing rationale
- $4.99: impulse buy — below psychological $5 barrier
- $10: "two coffees" framing — easy upsell from $4.99
- $50: positioned as tool, not content — "build on top of it"

---

## 🎬 Demo + Onboarding (Phase 5)

### Per-tier video demos
- 15–30 sec animation per tier showing what you get
- Placeholder CTA buttons on pricing page → `#video-tier-N` anchor
- Create with Cursor agent later; use placeholder div for now

### Demo stock pages (Phase 4 — Cursor to build)
- `/stocks/NOW` — ServiceNow crash score demo
- `/stocks/MU` — Micron memory cycle demo
- These are DEMO-ONLY: static data, not live pipeline
- Purpose: show $50 tier value; link from pricing page
- UI: same as main dashboard but with stock-specific framing
  - "NVDA fragility driven by: capex dependency, insider sell ratio, options flow"

### Walkthrough / tour
- After first login (free): 3-step tour overlay
  - Step 1: CRS zone bar explained
  - Step 2: Factor breakdown — what L/V/S/B/C mean
  - Step 3: Upgrade prompt to unlock S/B/C
- Use a simple state machine: `tour_step` in localStorage

---

## 🌍 Internationalisation (Phase 4)

### Languages
- EN (default), ZH-CN, MS
- Home: single cycle button via `common.js` (`cassandra-lang` in localStorage)
- Newspaper: golden hardcoded bodies in `newspaper-bodies.js` until pipeline stores per-lang editions
- Pricing: English-only until wired (lang button hidden)

### Agent / platform playgrounds
- Platform cards link to docs or stock desk demos
- Ungated RAG chat deferred until gate + grounding are production-ready
- See homepage `#agent-chat` gate stub (`/api/agent/gate`)

---

## 🔧 Technical debt

- `confidence_band()` unit test: assert `score.band_halfwidth > score_at_full_cov.band_halfwidth`
- `/api/run` should also require X-Pipeline-Key in prod (not just localhost hide)
- Worker secrets: rotate CF_KV_SECRET every 90 days
- Gemini model: migrate `gemini-2.5-flash-image` → `gemini-3.1-flash-image-preview` before Oct 2026
- SQLite: add WAL mode (`PRAGMA journal_mode=WAL`) for concurrent reads during pipeline write
- Email: choose between ConvertKit / Beehiiv / Resend for transactional + newsletter
  - Resend recommended: $0/month up to 3,000 emails/month, simple API, works with Supabase

---

## 💳 Payments todo

- [ ] Stripe: create product + price IDs for $4.99 and $10
- [ ] Stripe: webhook for `customer.subscription.created` → update Supabase tier
- [ ] Billplz: create collection → get collection ID → put in config.js
- [ ] Airwallex: apply for merchant account → get client_id/secret → put in .env (server-side only)
- [ ] All: payment confirmation page at `/subscribe/success?session_id=xxx`
- [ ] DuitNow QR: generate static QR via Billplz dashboard → save as `public/duitnow-qr.png`

---

## 🅰️ A/B tests to run eventually

- Headline framing: "AI Sector Fragility Monitor" vs "Will AI Crash?" — measure conversion
- CTA placement: above vs below the zone bar
- Countdown timer: visible vs hidden — does urgency help subscription?
- Price anchor: show $50 tier first (anchor) then $4.99 looks cheap

---

*This file is Cursor's memory for deferred work. Before every new session, review and move items to the active sprint if ready.*
