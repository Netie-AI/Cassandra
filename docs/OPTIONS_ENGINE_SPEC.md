# OPTIONS_ENGINE_SPEC

Turns a directional thesis into a ranked, gated shortlist of OTM put/call candidates. Decision-support
only — no execution, and it returns NO TRADE by default. Implemented in `src/options_engine.py`
(tested). This doc is the why.

## The core claim

The market prices a move through implied vol. Your thesis implies a **different** terminal
distribution — specifically a fat left tail (the crash leg) a plain lognormal omits. Edge exists only
where YOUR probability of finishing ITM exceeds the MARKET's risk-neutral probability. If it doesn't,
there is no trade — the market already agrees with you and you're paying full freight.

```
edge = P_thesis(finish ITM)  −  P_market(finish ITM)
```
`P_market` = Black-Scholes `N(d2)` (call) / `N(−d2)` (put). `P_thesis` = Monte-Carlo over the
jump-diffusion thesis distribution.

## The thesis distribution (why jump-diffusion)

A lognormal diffusion cannot express "20% chance of a 35% gap down." The whole bear thesis IS that
tail. So the terminal price is simulated as **diffusion + a Poisson jump**:
- diffusion: drift `μ_view`, vol `σ_diffuse` (your view, can differ from market IV)
- jumps: count ~ `Poisson(λ·T)`; each jump multiplies price by `(1 + N(jump_mean, jump_sd))`,
  with `jump_mean` negative for the crash leg (e.g. −0.35).

This is Merton-flavored and it's the right tool: it puts probability mass exactly where the thesis
says the market is complacent — the left tail.

## Three horizons (mapped to your near / far / long)

| Bucket | DTE | Character | When it's allowed |
|---|---|---|---|
| NEAR | ~7 | high gamma + high theta | **only with a DATED catalyst inside the expiry** (else theta bleed) |
| MID | ~90 | balanced | catalyst expected within a quarter |
| FAR | ~365 (LEAPS) | low theta, survives timing error | **the default for the structural CRS thesis** |

The horizon rule encodes the lesson from the whole conversation: being structurally right and
tactically early is how you lose. The structural thesis goes in LEAPS that survive the bull-trap
whipsaw; near-dated weeklies are reserved for *dated* events.

## Expected value and sizing

```
EV_per_contract = E_thesis[ payoff(S_T) ] − premium
EV_multiple     = EV_per_contract / premium        # expected return on premium under your distribution
kelly_fraction  = capped, never advice             # for relative sizing intuition only
```
Payoff integrated over the simulated terminal distribution (OTM put: `max(K − S_T, 0)`).

## The NO-TRADE gate (strict by design — most days return NO TRADE)

All must pass (`GATES` in code, tunable in config):
- `conviction ≥ 0.60` (from CRS confidence / event certainty)
- `edge ≥ 0.08` (your prob ITM beats market's by ≥8 points)
- `EV_multiple ≥ 0.25` (expected ≥ +25% on premium under your own distribution)
- NEAR horizon → requires `has_dated_catalyst_within_expiry == True`

Fail any → `verdict = "NO TRADE: <reason>"`. The self-test demonstrates a weekly OTM put rejected for
`edge -0.02` + `theta 12.8%/day` while a 12-month LEAPS passes with `edge +0.30, EV× +1.03`.

## Theta honesty (the "bet every day until the event" trap)

For any hold-or-rebuy-daily pattern, the engine surfaces `theta_per_day_pct` and warns when daily decay
compounds faster than the catalyst can plausibly arrive. Buying weekly OTM every day until a vague
"something will happen" is a bleed; the tool says so in numbers. Only a *dated* catalyst within the
expiry justifies the near-dated path.

## The next-day learning loop (Phase 7)

1. Persist every ranked candidate with its predicted edge/EV and the thesis snapshot.
2. Next session: pull the realized option mid + underlying move.
3. Compare predicted vs realized; classify the miss: **direction** (underlying went the other way),
   **timing** (right direction, too early — theta ate it), or **vol** (IV crush/expansion dominated).
4. Feed an error report to the orchestrator: "prediction was wrong because <class>." Over time, the
   attribution tunes the `ThesisView` mapping (e.g. if misses are mostly *timing*, push horizon longer
   and tighten the near-dated gate). Keep the attribution honest — log the losses, don't hide them.

## Candidate universe

Top-10 semiconductor + top-10 tech names (config `basket`) — the most liquid, highest-valuation,
cleanest OTM chains. Pull chains for the three horizons, build `OptionCandidate`s with live IV/premium,
rank. Skip names with wide spreads or thin OI (uncomputable edge → exclude, don't guess).
