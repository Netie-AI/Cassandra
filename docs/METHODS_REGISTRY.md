# METHODS_REGISTRY

Pluggable scoring methods. Selected via `config/settings.yaml`:

```yaml
method: crs_v1          # single method
# OR
ensemble: [crs_v1, sentiment_analog, breadth_momentum]
ensemble_weights: {crs_v1: 0.5, sentiment_analog: 0.3, breadth_momentum: 0.2}
```

Implementation: `src/methods.py`. The orchestrator reads config and calls `get()` or `ensemble()`.

---

## Registered methods

| Name | Source | What it scores | Direction |
|------|--------|----------------|-----------|
| `crs_v1` | `scoring.compute_crs` | Fragility×trigger CRS (default) | bearish if CRS ≥ 55 |
| `sentiment_analog` | `sentiment_analog.assess` | Historical crash resemblance → 0..100 | bearish if score ≥ 55 |
| `breadth_momentum` | breadth + phase inputs | Distribution / divergence only | bearish if divergence > 0.5 |

---

## Ensemble behavior

- Weighted average of member scores
- Confidence penalized by score spread between members
- Report **must** state disagreement when spread is wide

---

## To add a method

1. Implement `Method` protocol in `src/methods.py` (or new module)
2. Decorate with `@register("name")`
3. Document here with inputs, outputs, and when to use
4. Add self-test or fixture
5. Wire config key

---

## Planned (Phase 6+)

| Name | Idea | Status |
|------|------|--------|
| `vol_regime` | IV term structure + skew regime shift detector | not implemented |
| `liquidity_drain` | Net liquidity + RRP + TGA composite | not implemented |
