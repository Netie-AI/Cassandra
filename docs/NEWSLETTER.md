# Cassandra daily newsletter

Research desk email. Not financial advice. Dry-run is the default so a
mistaken command cannot mail a live audience.

## Command

```bash
# Default: print per-tier bodies (free / report / briefing / agent). Sends nothing.
python -m src.newsletter.send

# Same, explicit:
python -m src.newsletter.send --dry-run

# Live send (ops only, after reviewing dry-run). Requires RESEND_API_KEY or SMTP_*.
python -m src.newsletter.send --live
```

`--dry-run` is the default. `--live` is the documented live flag. This PR
does not send to a live audience.

Batch send respects `effective_tier`:

| effective_tier | Body |
|---|---|
| free | Short summary. L + V only. S / B / C locked. |
| report | Full 5-factor + capex NLP + analog. |
| briefing | Report plus 10-page / 2000-2008 analog + sources. |
| agent | Briefing plus watchlist / JSON API / chat 50/day note. |

Registered accounts use `trial_max_until = created_at + 90 days` (Agent, no
charge). Digest-only emails without an account stay Free.

## Schedule (MYT = Asia/Kuala_Lumpur, UTC+8)

Laptop xml Task Scheduler stubs already exist at 0545 / 0600 / 1800 MYT.
The cloud VM does **not** require Windows Task Scheduler. Use cron:

```cron
# 05:45 MYT = 21:45 UTC previous calendar day
45 21 * * 1-5  cd /opt/cassandra && python -m src.newsletter.send --dry-run

# 06:00 MYT = 22:00 UTC previous calendar day
0 22 * * 1-5   cd /opt/cassandra && python -m src.newsletter.send --dry-run

# 18:00 MYT = 10:00 UTC same calendar day
0 10 * * 1-5   cd /opt/cassandra && python -m src.newsletter.send --dry-run
```

Weekdays only here as a starting point. Trading-day skip still belongs to
`calendar_guard` on the pipeline, not this mailer.

Ops HTTP: `POST /api/newsletter/dispatch` defaults to dry-run. Pass
`{"live": true}` plus `X-Pipeline-Key` to send. `POST /api/ops/newsletter/send`
is the gated live path on the laptop ops desk.

Phase 16 Resend audience sync remains: `RESEND_API_KEY` + optional
`RESEND_AUDIENCE_ID`. Auth is still stub until `SUPABASE_SERVICE_ROLE_KEY`
and `SUPABASE_JWT_SECRET` are set.
