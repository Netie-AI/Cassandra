# CRASH_SCORE_SPEC

The full math behind the Crash Risk Score (CRS). This is the document to verify first. Every number
the system emits traces back to a formula here. `src/scoring.py` implements §1–§6 and §8; §9 is a
worked example that the implementation must reproduce exactly.

Design constraints:
- **Auditable.** No black box. Every metric has a source, a direction, and a weight you can see.
- **Robust.** Logistic squashing so single outliers can't dominate; percentile fallback for
  non-normal metrics.
- **Honest about the two regimes.** Fragility and Trigger are separated and recombined with an
  interaction term, so "loaded spring" ≠ "fired spring."
- **Falsifiable.** The score moves on observable inputs; the report states what would flip it.

---

## §1 — Factor taxonomy

Five buckets. Four compose **Fragility (F)**; the fifth is **Trigger (T)**, kept separate.

| Factor | Symbol | Role | Example metrics |
|---|---|---|---|
| Leverage | L | Fragility | margin-debt YoY, margin/mktcap, credit spread (inv.), AI-cohort net debt-funded capex |
| Valuation | V | Fragility | cohort fwd P/S vs hist, market-cap/GDP, top-10 concentration, ERP (inv.) |
| Sentiment/Positioning | S | Fragility | put/call (inv.), retail net-call streak, IV skew, AAII/Fear&Greed, [BTC MVRV-Z, NUPL] |
| Breadth/Internals | B | Fragility | % > 200dma, new highs−lows, index/breadth divergence, A/D slope |
| Catalyst | C | **Trigger** | Fed hike-odds, supply-side tells, capex-cut NLP, capex/rev gap slope, net-liquidity/MOVE |

Each metric `i` carries a **directionality** `s_i ∈ {+1, −1}`: `+1` if higher raw value = more
bearish, `−1` if higher = more bullish (those get sign-flipped). Example: margin-debt YoY is `+1`;
% > 200dma is `−1`.

---

## §2 — Normalization (raw metric → [0,1])

For each metric, take a rolling history of window `W` (default 3y daily, or longest available; monthly
series like margin debt use their own native cadence).

**Z-score:**
```
z_i = (x_i − μ_{i,W}) / σ_{i,W}
```

**Apply direction, then logistic squash to [0,1]:**
```
n_i = 1 / (1 + exp(−k · s_i · z_i))
```
`k` = steepness (default `1.2`). Logistic is chosen over min-max so a single record print saturates
near 1 instead of rescaling every other reading. `n_i = 0.5` means "at its historical mean."

**Non-normal override.** Metrics with fat tails or hard theoretical thresholds (e.g. BTC MVRV-Z,
where the literature flags `>7` as a top marker) use **empirical percentile rank** instead of z:
```
n_i = directional_percentile_rank(x_i, history)   # ∈ [0,1]
```
plus an optional hard-threshold bonus: if `x_i` crosses a documented extreme, floor `n_i` at e.g.
0.9. Config flag `use_percentile: true` per metric.

**Missing data.** If a metric can't be pulled, `n_i = None`. It is dropped from its factor's weighted
mean (weights renormalize over present metrics) and flagged for the confidence penalty (§8).

---

## §3 — Factor aggregation

Within each factor, weighted mean over present metrics:
```
L = Σ_i (w_{L,i} · n_{L,i}) / Σ_i w_{L,i}      # over present i
```
identically for V, S, B, C. Intra-factor weights live in config; defaults in §7.

Each factor score ∈ [0,1].

---

## §4 — Fragility and Trigger

```
F = w_L·L + w_V·V + w_S·S + w_B·B          (w_L + w_V + w_S + w_B = 1)
T = C
```

Default factor weights (justified in §7):
```
w_L = 0.30   w_B = 0.25   w_V = 0.25   w_S = 0.20
```
Leverage and Breadth carry the most weight because they are the most mechanically reliable
(forced-selling fuel and internal-distribution fingerprint). Sentiment carries the least because it
is the noisiest and most prone to "stay irrational longer than you can stay solvent."

`F, T ∈ [0,1]`.

---

## §5 — Crash Risk Score (the interaction model)

```
CRS_raw = a·F + b·T + c·(F · T)
CRS     = 100 · CRS_raw
```
with
```
a = 0.35   b = 0.20   c = 0.45        (a + b + c = 1)
```

Properties (these are the whole point — verify them):
- `F=1, T=1  → CRS_raw = 0.35+0.20+0.45 = 1.00 → CRS = 100`   (max)
- `F=1, T=0  → CRS_raw = 0.35            → CRS = 35`    (fully loaded spring, no spark → elevated, not imminent)
- `F=0, T=1  → CRS_raw = 0.20            → CRS = 20`    (a spark with nothing loaded → little happens)
- `F=0.5,T=0.5 → 0.175+0.10+0.1125 = 0.3875 → CRS ≈ 39`
- `F=0.8,T=0.8 → 0.28+0.16+0.288 = 0.728 → CRS ≈ 73`    (interaction ignites)

The `c·F·T` term is the mathematical statement of "a crash needs both." It is the single most
important line in this spec. Without it the model would scream during every overvalued-but-stable
stretch and get you chopped up.

**Interpretation bands:**

| CRS | Band | Read |
|---|---|---|
| 0–25 | Benign | Accumulation-compatible; no edge to bearish positioning |
| 25–45 | Awareness | Fragility building; trigger dormant. Watch, don't act |
| 45–65 | Mania | Loaded spring. Hedge cheap, build the survivor buy-list |
| 65–80 | Distribution / Danger | Both elevated. Defined-risk downside earns its place |
| 80–100 | Blow-off risk | Forced-liquidation conditions present. The tape leads, not the score |

---

## §6 — Fragility momentum (the time-correction)

Answers "does risk decay if months pass quietly?" — only if fragility is actually falling.
```
dF/dt = OLS_slope( F_{t−n..t} )       # default n = 10 trading days
```
Report alongside CRS:
- `dF/dt > +ε` → **loading** → no decay; if CRS high and rising, conviction increases.
- `|dF/dt| ≤ ε` → **plateau** → CRS taken at face value.
- `dF/dt < −ε` → **bleeding off** → the *imminence* of a high CRS is decaying even if the level
  is still high (spring unwinding). This is the only condition that lowers urgency.

`ε` default `0.005 / day`. The output object carries `momentum_state ∈ {loading, plateau, bleeding}`.
Calendar time never decays the score. Only `dF/dt` does.

---

## §7 — Default weights and their justification

Intra-factor weights (config-overridable). Rationale is the part to argue with:

**Leverage L** — `margin_yoy 0.35, margin_to_mktcap 0.25, credit_spread_inv 0.20, debt_capex 0.20`.
Margin YoY leads tops historically (peaked ahead of 2000/2007/2021). Spread *tightness* is
complacency fuel. Debt-funded capex is the AI-specific 2026 wrinkle (neoclouds, hyperscaler bonds).

**Breadth B** — `pct_above_200dma 0.30, new_high_low 0.25, index_breadth_divergence 0.30, ad_slope 0.15`.
Divergence (index high while internals rot) is the cleanest distribution tell, so it's weighted with
the level metrics, not below them.

**Valuation V** — `cohort_fwd_ps 0.35, mktcap_gdp 0.25, top10_concentration 0.20, erp_inv 0.20`.
Cohort forward P/S over the semis+hyperscaler basket is the direct 2026 read; concentration captures
index-fragility (one name's reset drags the tape).

**Sentiment S** — `put_call_inv 0.25, retail_call_streak 0.25, iv_skew 0.20, survey 0.15, crypto_mvrv 0.15`.
Crypto cross-read optional (`enable_crypto_crossread`), included small because MVRV-Z/NUPL are the
behavioral analog the source doc rightly flagged — but they're a *confirmation*, not a driver.

**Catalyst C (Trigger)** — `fed_path 0.30, supply_tells 0.25, capex_cut_nlp 0.25, capex_rev_gap_slope 0.10, net_liquidity 0.10`.
Fed path + supply tells + the capex-cut signal are the live 2026 triggers; the capex-cut NLP score is
the "Lehman moment" detector and is graded 0→1 from earnings-call language, not binary.

**Top-level** — `F-factors {L .30, B .25, V .25, S .20}`, `CRS {a .35, b .20, c .45}`.
All overridable in `settings.yaml`. **Backtest before trusting** (§10).

---

## §8 — Confidence band (never a bare point estimate)

```
confidence = clip( w_f·freshness + w_a·agreement + w_c·coverage , 0, 1 )
band_halfwidth = (1 − confidence) · MAX_BAND        # MAX_BAND default 12 CRS points
report:  CRS = X  ( ±band_halfwidth ),  confidence = {low|med|high}
```
- **freshness** — penalize stale inputs by their lag (margin debt is monthly → its contribution to
  freshness decays over the month). `freshness = mean(exp(−age_days/τ_i))`.
- **agreement** — `1 − normalized_stdev([L,V,S,B,C])`. If factors disagree, the band widens. A
  high CRS driven only by valuation while breadth is fine is *less* trustworthy than one where all
  four fragility factors point together.
- **coverage** — fraction of metrics successfully pulled today.

Weights `w_f .35, w_a .40, w_c .25`. Agreement is weighted highest: a confident score is one where
independent evidence domains *converge*.

---

## §9 — Worked example (the implementation must reproduce this)

Inputs (already normalized to `n_i ∈ [0,1]`; in production §2 produces these):

```
Leverage:    margin_yoy 0.88  margin_to_mktcap 0.80  credit_spread_inv 0.75  debt_capex 0.70
Breadth:     pct_above_200dma 0.55  new_high_low 0.62  divergence 0.70  ad_slope 0.50
Valuation:   cohort_fwd_ps 0.78  mktcap_gdp 0.82  top10_concentration 0.85  erp_inv 0.72
Sentiment:   put_call_inv 0.60  retail_call_streak 0.80  iv_skew 0.45  survey 0.55  crypto_mvrv 0.40
Catalyst:    fed_path 0.90  supply_tells 0.65  capex_cut_nlp 0.30  capex_rev_gap_slope 0.60  net_liq 0.55
```

Using §7 default intra-factor weights:

```
L = (.35·.88 + .25·.80 + .20·.75 + .20·.70) / 1.00 = 0.798
B = (.30·.55 + .25·.62 + .30·.70 + .15·.50) / 1.00 = 0.605
V = (.35·.78 + .25·.82 + .20·.85 + .20·.72) / 1.00 = 0.792
S = (.25·.60 + .25·.80 + .20·.45 + .15·.55 + .15·.40) / 1.00 = 0.5825
C = (.30·.90 + .25·.65 + .25·.30 + .10·.60 + .10·.55) / 1.00 = 0.6225
```

Fragility and Trigger (§4 weights `L .30 V .25 S .20 B .25`):
```
F = .30·0.798 + .25·0.792 + .20·0.5825 + .25·0.605
  = 0.2394 + 0.1980 + 0.1165 + 0.15125 = 0.7052
T = C = 0.6225
```

CRS (§5, `a .35 b .20 c .45`):
```
CRS_raw = .35·0.7052 + .20·0.6225 + .45·(0.7052·0.6225)
        = 0.24682 + 0.12450 + 0.45·0.43899
        = 0.24682 + 0.12450 + 0.19755
        = 0.56887
CRS = 56.9
```

**Result: CRS ≈ 57 → "Mania" band.** Fragility is high (0.71) and the spring is loaded, but the
Trigger (0.62) is dragged down by `capex_cut_nlp = 0.30` — no hyperscaler has formally cut guidance
yet. The interaction term contributes ~20 pts. If `capex_cut_nlp` jumped to 0.85 (a real cut), C rises
to 0.760, T = 0.760, and:
```
CRS_raw = .35·0.7052 + .20·0.760 + .45·(0.7052·0.760) = 0.24682 + 0.1520 + 0.24118 = 0.6400
CRS = 64.0   → top of Mania, edging into Danger
```
That sensitivity is the model working: the Lehman-moment input is the swing variable, exactly as it
is in reality.

`scoring.py` ships a unit test asserting `abs(crs - 56.9) < 0.1` on these inputs.

---

## §10 — Calibration & backtest (mandatory before trusting with size)

1. Assemble history for every metric back through ≥ 2018 (covers 2018 vol, 2020 crash, 2021 top,
   2022 bear, 2025 DeepSeek shock).
2. Replay daily; record CRS.
3. Check the score *led* known stress (rose into Q4-2021, Jan-2025) and *fell* into recoveries.
4. Tune weights to maximize separation between pre-crash and benign regimes **without overfitting** —
   prefer fewer, well-motivated weights over a fitted zoo. If a weight only helps in-sample, cut it.
5. Report the score's hit/false-alarm profile honestly in the daily header ("this gauge has fired
   N times historically; M preceded >10% drawdowns"). A gauge you can't characterize, you can't trust.

The CRS is a *hypothesis about fragility*, not a fact. The math is exact; the mapping from math to the
future is not. Keep that line bright.
