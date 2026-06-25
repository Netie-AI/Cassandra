# SENTIMENT_ANALOG_SPEC

"Which historical crash, and how many months before it, does today resemble?" Implemented in
`src/sentiment_analog.py` (tested). Read the warning first.

## ⚠ The honesty warning (this is a gauge, not a clock)

There are ~3–4 usable historical crashes (Cisco/dot-com 2000, GFC 2007–08, 2021 top, + 2025 DeepSeek
as a near-miss). A high-dimensional feature vector over 3 samples is the curse of dimensionality. The
"T-minus N days before <event>" number is an **estimate with a wide band**, never a countdown. Its job
is to make you ask "today looks like 3 months before Cisco — is the resemblance real, or is the regime
different?" — not to tell you the date. Divergence from the analog is **information to attribute**, not
a failure to hide.

## Feature vector

A fixed-order vector per day (same axes for today and every historical day):
`[news_sentiment, put_call, pct_above_200dma, vix_level, margin_yoy, cohort_fwd_ps_z,
capex_cut_signal, breadth_divergence]`. Sourced from the live subagent outputs. Normalized against a
baseline (z-score) so axes are comparable.

## Distance + nearest analog

For today's vector `v_t`, distance to each labeled historical day `h` (Euclidean, or Mahalanobis if a
covariance is supplied to de-correlate axes). k-NN (default k=8), inverse-distance weighted, gives:
- the **nearest event** (modal among neighbors), and
- an **estimated days-before-peak** (weighted mean of neighbors' labels) with a **spread** (their
  weighted std = the disagreement, which becomes part of the band).

## Gaussian smoothing (denoise the daily estimate)

The raw daily estimate jitters. Smooth the recent series with a Gaussian kernel centered on today:
```
ŝ_t = Σ_i w_i · s_i ,   w_i ∝ exp(−½((i − t)/σ)²)
```
`σ` default 3 days. Report the smoothed value as the headline estimate, the raw as a secondary, and the
neighbor-spread + regime penalty as the band.

## Regime warnings (what makes the analogy honest)

Flags that widen the band and print loudly:
- `hyperscalers_cashrich` — 2026 buyers fund capex from cash flow; 2000 dot-coms didn't → analog may
  **overstate** fragility.
- `etf_structural_bid` — passive flows absent in older analogs → tops can stretch **longer** than the
  analog implies.
- `rates_regime_differs` — discounting dynamics not comparable.

Confidence shrinks with neighbor disagreement and the number of regime warnings. A resemblance with two
active regime warnings is explicitly low-confidence.

## The error-attribution loop (self-correction)

Runs on a 30-day lag. If the analog implied imminence (`est_days_before < 45`) but the next month was
benign, log the miss, attribute it (usually a named regime difference), and **down-weight** that analog
(×0.85). If a break arrived earlier than the analog suggested, **up-weight** it (×1.10). This is the
"explain why we were wrong and update" mechanism — it turns each miss into a recorded, attributed
weight adjustment rather than a silent failure. The attribution string goes into the daily report.

## Output → methods layer

Mapped to a 0–100 "closeness to a known top" score via `methods.py::sentiment_analog` (180d→0,
0d→100), so it can run standalone or be ensembled with `crs_v1`. When the two **agree** (CRS high +
analog says "near a top" + phase classifier says Distribution), conviction is highest. When they
disagree, the report says so and confidence drops.

## Data work (Phase 5)

Replace the seed library with **real** historical feature vectors: reconstruct each axis for the
pre-crash windows from archival data (sentiment indices, put/call history, breadth, VIX, FINRA margin,
valuation). This is the bulk of the work and the part that determines whether the analog is meaningful
or noise. Document every reconstructed source.
