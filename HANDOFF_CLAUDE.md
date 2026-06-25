# HANDOFF → Next Claude session
**Read this file and the orchestrator.py Cursor pastes. Nothing else.**

---

## Your job this window

Cursor will paste `src/orchestrator.py` (or its current stub). You:

1. Review it against the architecture spec below
2. Confirm the 5-subagent dispatch pattern is correct
3. APPROVED → Cursor wires live data flow
4. Deliver the capex_cut grader calibration set (already written below — just confirm/adjust and hand to Cursor)

---

## Current state (Phase 4 APPROVED)

| Layer | Status | File |
|---|---|---|
| Pipeline | ✅ | src/pipeline.py |
| Scoring | ✅ CRS=56.9 regression | src/scoring.py |
| Store | ✅ | src/store.py |
| Report | ✅ | src/report.py (Gemini 2.5 Flash) |
| Dashboard | ✅ EN/ZH/MS, dark/light | web/static/ |
| Newspaper | ✅ NYT layout + share | web/static/newspaper-report.html |
| CF Worker | ✅ | cloudflare/worker.js |
| Stock demos | ✅ static placeholders | /stocks/NOW, /stocks/MU |
| Tier gating | ✅ stub | api/auth.py |
| Orchestrator | ⏳ WIRE: | src/orchestrator.py — THIS WINDOW |

---

## Orchestrator architecture (what you are reviewing)

```
Orchestrator (claude-opus-4-8 via OpenRouter or direct Anthropic)
    │
    ├── dispatches PARALLEL to 5 subagents (claude-sonnet-4-6)
    │       News Digestor      → NewsRead (capex_cut_signal, supply_tell)
    │       Market Structure   → StructureRead (breadth, vix, put_call)
    │       Derivatives/Flow   → FlowRead (flow, dark pool, options)
    │       Whale/Smart Money  → WhaleRead (insider, 13F, whale buys)
    │       Fundamentals       → FragilityRead (FRED, margin, valuation)
    │
    ├── collects all ReadResults
    ├── calls scoring.compute_crs(normalized, freshness, coverage, weights)
    │       PURE PYTHON — no LLM touches the math
    ├── calls phase.classify(ohlcv)
    │       PURE PYTHON — no LLM
    │
    ├── calls report.generate(score, reads) → Gemini 2.5 Flash
    ├── calls store.save_score() + store.save_metrics()
    └── calls cf_publish.publish_score()
```

### Hard rules to check in orchestrator.py

| Rule | Check |
|---|---|
| LLM never computes CRS | Only `scoring.compute_crs()` does math |
| Subagents return structured read objects, not prose | `NewsRead`, `StructureRead`, etc. — not free text |
| Fallback on subagent failure | Each subagent wrapped in try/except; pipeline continues with partial data |
| Coverage honest | Missing subagents reduce `coverage` input to `compute_crs` |
| No trade | No method that places, suggests, or sizes a trade |
| Calendar gate | `calendar_guard.should_run()` checked before dispatch |
| 3× daily | Schedule: 04:00 / 13:00 / 16:00 UTC (matches 00:00 / 09:00 / 12:00 MYT) |

---

## capex_cut grader calibration

**This is your primary deliverable for this window.**

The `capex_cut_nlp` signal is the Lehman moment detector. It feeds directly into
`Trigger (T)` in `scoring.compute_crs()`. If this fires wrong, the whole CRS is wrong.

### Scoring rubric

```
0.80–1.0  FIRE: Explicit guidance cut with specifics, "pause", "halt", "reduce",
          "freeze", "reassess". Named projects being stopped. Forward-looking.
          Any formal capex guidance reduction in dollar terms.

0.55–0.79 CONCERN: "Moderate pace", "temper", "slow", "flexible timing",
          "disciplined deployment", "watching closely", "data-driven".
          Clear pullback signal; no formal cut yet.

0.35–0.54 AMBIGUOUS: Commitment with notable caveats. "Thoughtful about pacing
          while remaining committed." Could go either way.

0.15–0.34 NEUTRAL-CAUTIOUS: Standard guidance language, minor caution.
          Plan unchanged. Capital efficiency mentioned.

0.00–0.14 GROWTH: Explicit capex increase, raised guidance, acceleration,
          "generational opportunity", strong bullish signal.
```

**Critical rules:**
- Score FORWARD-LOOKING language only. "We reduced capex last quarter" (past) → lower
  score than "We are reducing capex" (present/future cut signal).
- Applies ONLY to hyperscaler AI / data-center capex: Microsoft Azure/AI, Amazon AWS,
  Google GCP/TPU, Meta AI infra, Oracle Cloud, CoreWeave, xAI infra.
- Non-AI capex (retail warehouses, physical stores) → score 0.0 (not relevant).
- Single company = one score per earnings call per quarter.

---

### Calibration set (10 snippets) — confirm and hand to Cursor

```python
CAPEX_CUT_CALIBRATION = [
    {
        "id": "cc_01",
        "source": "Microsoft Q2 2026 earnings call (synthetic calibration example)",
        "snippet": (
            "Given meaningfully weaker-than-expected enterprise AI adoption, we are "
            "reducing our full-year fiscal 2026 capital expenditure guidance to "
            "approximately $68 billion, down from our prior estimate of $80 billion. "
            "We are pausing planned Azure data center expansions in EMEA and APAC "
            "and will reassess the pace of deployment based on Q3 demand signals."
        ),
        "expected_score": 0.93,
        "reasoning": (
            "Explicit dollar-figure reduction ($80B→$68B), named region pauses, "
            "and formal guidance cut. Maximum fire signal."
        ),
    },
    {
        "id": "cc_02",
        "source": "Amazon Q4 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We have made the decision to significantly curtail our data center "
            "infrastructure investment plans for the remainder of the calendar year. "
            "The pace of AI workload growth has not met our internal expectations, "
            "and we believe the prudent course is to slow our build-out materially "
            "until we have better visibility on capacity utilization rates."
        ),
        "expected_score": 0.86,
        "reasoning": (
            "Strong cut language ('curtail', 'slow materially') and explicit demand "
            "shortfall admission. No hard dollar figure but forward-looking reduction."
        ),
    },
    {
        "id": "cc_03",
        "source": "Google Q1 2026 earnings call (synthetic calibration example)",
        "snippet": (
            "We're being more disciplined about the timing of our TPU and data center "
            "investments. While we still expect to hit our multi-year build targets, "
            "we are moderating the pace of near-term deployment given the current "
            "demand environment. Certain projects have shifted to the right by one to "
            "two quarters."
        ),
        "expected_score": 0.71,
        "reasoning": (
            "Clear moderation language ('moderating pace', 'shifted to the right') "
            "without explicit guidance cut. Projects delayed, not cancelled. Mid-range "
            "concern signal."
        ),
    },
    {
        "id": "cc_04",
        "source": "Meta Q3 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We continue to monitor our AI infrastructure capacity utilization closely. "
            "Our capital deployment will remain data-driven, and we have flexibility in "
            "the timing of certain projects. We've asked our teams to rigorously "
            "prioritize their investment requests given the macro environment."
        ),
        "expected_score": 0.55,
        "reasoning": (
            "Ambiguous — 'monitoring closely', 'flexibility in timing', 'prioritize' "
            "all suggest caution but no formal change. Sits at the concern/ambiguous "
            "boundary. Trend watching required."
        ),
    },
    {
        "id": "cc_05",
        "source": "Microsoft Q3 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "While we're watching demand signals carefully, we remain fully committed "
            "to our infrastructure investment plan. We believe these investments are "
            "critical for long-term competitiveness in AI. That said, we are being "
            "thoughtful about pacing to ensure we're deploying capital efficiently."
        ),
        "expected_score": 0.42,
        "reasoning": (
            "Mixed: 'committed' directly contradicts 'thoughtful about pacing'. "
            "Ambiguous mid-range. No actionable cut signal yet."
        ),
    },
    {
        "id": "cc_06",
        "source": "Amazon Q2 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "Our capital expenditure guidance for 2025 remains unchanged at "
            "approximately $105 billion. We have high confidence in the long-term "
            "demand trajectory for AWS. We'll continue to stay disciplined as always "
            "in how we deploy capital."
        ),
        "expected_score": 0.22,
        "reasoning": (
            "Explicit 'unchanged' guidance confirmation. 'High confidence' framing. "
            "Boilerplate 'disciplined' does not constitute a signal. Low score."
        ),
    },
    {
        "id": "cc_07",
        "source": "Google Q2 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We remain on track with our global data center build-out. Customer "
            "demand for Google Cloud and AI services continues to be strong, and "
            "we're focused on meeting our commitments. We continue to evaluate "
            "the best ways to optimize our investment efficiency."
        ),
        "expected_score": 0.14,
        "reasoning": (
            "'On track', 'demand strong', 'meeting commitments'. Purely positive "
            "maintenance language. 'Optimize efficiency' is generic. Near-zero signal."
        ),
    },
    {
        "id": "cc_08",
        "source": "Microsoft Q1 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "Capital expenditure for fiscal year 2025 is expected to be approximately "
            "$80 billion, consistent with our prior guidance. We are expanding capacity "
            "across Azure regions to meet robust customer demand for AI services."
        ),
        "expected_score": 0.08,
        "reasoning": (
            "Flat 'consistent with prior guidance' + 'expanding capacity'. "
            "Pure maintenance signal. No concern language whatsoever."
        ),
    },
    {
        "id": "cc_09",
        "source": "Amazon Q1 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We are accelerating our data center investments in response to "
            "demand that has exceeded our forecasts. We've committed to an additional "
            "$15 billion in AWS infrastructure spending beyond our original plan, "
            "bringing full-year capex to approximately $120 billion."
        ),
        "expected_score": 0.04,
        "reasoning": (
            "Explicit acceleration + guidance raise. Strong bullish capex signal. "
            "Opposite of what we're detecting. Nearly zero cut signal."
        ),
    },
    {
        "id": "cc_10",
        "source": "Google Q4 2024 earnings call (synthetic calibration example)",
        "snippet": (
            "The AI opportunity is generational, and we intend to be the clear global "
            "leader. We are doubling our TPU cluster investments and have raised our "
            "five-year AI infrastructure commitment to $250 billion. We are deploying "
            "at the fastest pace in Google's history."
        ),
        "expected_score": 0.02,
        "reasoning": (
            "Maximum bullish signal: 'doubling', 'generational', '$250B commitment', "
            "'fastest pace in history'. Absolute zero on cut detection."
        ),
    },
]
```

### How Cursor wires this into the grader

The News Digestor subagent extracts snippets, then calls:

```python
# src/tools/capex_nlp.py
import json
from anthropic import Anthropic  # or via OpenRouter

RUBRIC = """
Score this earnings call snippet for AI/datacenter capex cut signal (0.0–1.0).

RUBRIC:
0.80–1.0: Explicit guidance cut, named pauses, dollar reductions (FIRE)
0.55–0.79: Pace moderation, 'flexible timing', demand shortfall (CONCERN)
0.35–0.54: Mixed commitment with notable caveats (AMBIGUOUS)
0.15–0.34: Standard unchanged guidance, minor caution (NEUTRAL)
0.00–0.14: Capex growth, raised guidance, acceleration (GROWTH)

Rules: Score FORWARD-LOOKING language only.
Only score hyperscaler AI/datacenter capex. Non-AI capex → 0.0.

Few-shot examples:
[PASTE THE 10 CALIBRATION SNIPPETS HERE WITH THEIR SCORES]

Respond with ONLY a JSON object: {"score": 0.XX, "reason": "one sentence"}
"""

def score_capex_cut(snippet: str, client: Anthropic) -> float:
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[
            {"role": "user", "content": f"{RUBRIC}\n\nSnippet to score:\n{snippet}"}
        ]
    )
    try:
        data = json.loads(resp.content[0].text)
        return float(data["score"])
    except Exception:
        return 0.5  # safe default on parse failure
```

---

## Review checklist for orchestrator.py

When Cursor pastes it, check these in order:

```
□ Imports: no LLM library imported at module level for scoring/phase
□ dispatch(): runs all 5 subagents with asyncio.gather or equivalent parallel call
□ Each subagent returns a typed Pydantic model (not raw string)
□ Exception handling: each subagent wrapped; failure = None in result
□ Coverage computed from: sum(r is not None for r in results) / 5
□ compute_crs() called with normalized dict — not raw agent prose
□ calendar_guard.should_run() checked before any API calls
□ report.generate() called AFTER scoring — score passes into report
□ save_score() + save_metrics() called AFTER report generation
□ publish_score() called last — if this fails, pipeline still completes
□ No method named trade/order/execute/position/buy/sell anywhere
```

---

## State for this handoff

| Item | Value |
|---|---|
| Last CRS | 38.8 · Awareness |
| Last F | 0.71 |
| Last T | 0.62 |
| capex_cut_nlp | 0.30 (no formal cut yet) |
| coverage | 0.40 |
| Phase | Distribution Range, 50% conf |
| Branch | phase4-ui-report → phase5-orchestrator (new branch) |
| Next action | Cursor pushes phase5-orchestrator branch → paste to Claude |

## Format reminder

Reply in CASSANDRA PROTOCOL format only:
`═══ CASSANDRA ════` header, GATE STATUS table, TO CURSOR list.
APPROVED or REJECT with exact line number to fix.
