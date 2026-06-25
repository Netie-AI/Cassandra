# CASSANDRA TIER SPEC + STOCK DEMO PAGES
> Cursor: implement in Phase 4. This is the source of truth for gating + demo pages.

---

## Tier gating in API

```python
# api/main.py — add after current /api/dashboard
from .auth import get_user_tier  # Supabase lookup by JWT

@app.get("/api/dashboard")
def dashboard(tier: str = Depends(get_user_tier)):
    score = latest_score()
    metrics = latest_metrics()
    if tier == "free":
        # Hide S, B, C factor values
        if score and "factors" in score:
            for f in ["sentiment", "breadth", "catalyst"]:
                score["factors"][f] = None  # client renders lock icon
    return {"score": score, "metrics": metrics, "tier": tier}
```

---

## Demo stock pages spec

### Route pattern
```
/stocks/<TICKER>   →   web/static/stocks/<TICKER>/index.html
```

### Tickers to build first (demo only, static data)
- `NOW` — ServiceNow
- `MU` — Micron Technology

### What each stock page shows (static placeholder data)
```json
{
  "ticker": "NOW",
  "name": "ServiceNow",
  "crs_stock": 51.2,
  "band": "Mania",
  "fragility_drivers": [
    "P/S ratio at 18× vs 5-year median 14×",
    "Insider sell ratio: 4.2× above average",
    "AI revenue dependency: 38% of forward guidance"
  ],
  "trigger_watch": [
    "Enterprise IT spend freeze signals",
    "Azure/AWS growth deceleration as demand proxy",
    "Fed rate path impact on SaaS multiples"
  ],
  "analog": "Salesforce Q2 2022 — 6 weeks before -55% drawdown",
  "note": "Demo only. Live data available at $50/month tier."
}
```

```json
{
  "ticker": "MU",
  "name": "Micron Technology",
  "crs_stock": 44.8,
  "band": "Awareness",
  "fragility_drivers": [
    "DRAM forward price curve inverted for first time since 2022",
    "HBM capacity build concentrated in 3 customers",
    "SK Hynix supply signals from Korean news sources"
  ],
  "trigger_watch": [
    "Samsung capex decision (Q3 2026 earnings)",
    "AI training cluster demand plateauing",
    "CHIPS Act subsidy timing vs fab ramp"
  ],
  "analog": "MU in Q3 2022 — 8 weeks before -45% drawdown",
  "note": "Demo only. Live data available at $50/month tier."
}
```

### Stock page HTML structure (Cursor to build)
- Same masthead as newspaper-report.html
- Stock ticker large, name smaller
- Stock-specific CRS displayed like main dashboard
- "Fragility drivers" as 3-bullet list (visible to demo)
- "Trigger watch" as 3-bullet list (visible to demo)
- Analog date (visible to demo)
- Bottom: "This is a demo. Subscribe at $50/month for live data."
- CTA: large button → /subscribe?tier=agent

### Demo intent
These pages exist to show the $50 tier value during the sales demo.
They are STATIC — no live pipeline data. No API calls.
They will be replaced with live data when the stock agent is built in Phase 5.

---

## Pricing page spec

### Route: /pricing or /subscribe

### Layout (top to bottom)
1. Header: "Choose your plan"
2. Four tier cards in a row (or 2×2 on mobile)
3. Each card:
   - Tier name (bold)
   - Price (large)
   - 3–5 bullet features
   - CTA button (Subscribe)
   - Video placeholder (15px gray div with play icon — fill later)
4. FAQ section (3 questions)
5. Payment methods row (Stripe / PayPal / Billplz / Alipay — auto-show based on geo)

### Tier card data
```
Free
$0/month
- Live CRS score + band
- L + V factor scores
- 3× daily updates
- Free email summary
[Access now →]

The Report
$4.99/month
- Everything in Free
- Full 5-factor daily report
- capex NLP signal
- Historical analog comparison
- Email delivery daily
[Subscribe →]

The Briefing  ← MOST POPULAR badge
$10/month
- Everything in Report
- 10-page deep analysis
- AI-generated insights
- Side-by-side 2000/2008 analog
- Source attribution on all data
[Subscribe →]

The Agent
$50/month
- Everything in Briefing
- Custom stock watchlist
- Stock-specific crash scores
- API access (JSON endpoint)
- Chat with CASSANDRA (50/day)
- Add-on credits: $5/500 calls
[Subscribe →]
```

---

## Supabase schema (implement when auth is ready)

```sql
-- Run in Supabase SQL editor
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email_hash TEXT UNIQUE NOT NULL,  -- SHA-256, never store plaintext
  tier TEXT NOT NULL DEFAULT 'free',
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id),
  provider TEXT,  -- 'stripe' | 'billplz' | 'airwallex'
  provider_ref TEXT,
  status TEXT DEFAULT 'active',  -- 'active' | 'cancelled' | 'past_due'
  tier TEXT NOT NULL,
  renews_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE report_sends (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id),
  report_date DATE NOT NULL,
  tier TEXT NOT NULL,
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  opened_at TIMESTAMPTZ
);
```

---

*Cursor: read this before building auth, pricing page, or stock demo pages.*
