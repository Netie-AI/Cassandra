"""
methods.py — the pluggable-method layer. The user wants to swap "different methods" for the same job
(score the regime, predict the phase, rank options). This is a tiny registry + a common protocol so a
method can be selected by name in config, or several can be ensembled and reconciled.

A "method" takes the day's evidence bundles and returns a directional/score read. Register new ones
without touching the orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class MethodOutput:
    name: str
    score: float                # 0..100 regime/crash score on a common scale
    direction: str              # "bearish" | "bullish" | "neutral"
    confidence: float           # 0..1
    detail: dict                # method-specific internals for the report


class Method(Protocol):
    def __call__(self, evidence: dict) -> MethodOutput: ...


_REGISTRY: dict[str, Method] = {}


def register(name: str) -> Callable[[Method], Method]:
    def deco(fn: Method) -> Method:
        _REGISTRY[name] = fn
        return fn
    return deco


def get(name: str) -> Method:
    if name not in _REGISTRY:
        raise KeyError(f"unknown method '{name}'. registered: {list(_REGISTRY)}")
    return _REGISTRY[name]


def available() -> list[str]:
    return list(_REGISTRY)


def ensemble(names: list[str], evidence: dict, weights: dict[str, float] | None = None) -> MethodOutput:
    """Run several methods and reconcile. Disagreement lowers confidence (and the report must say so)."""
    weights = weights or {n: 1.0 for n in names}
    outs = [get(n)(evidence) for n in names]
    wsum = sum(weights[o.name] for o in outs)
    score = sum(o.score * weights[o.name] for o in outs) / wsum
    # confidence penalized by disagreement in score
    import statistics
    spread = statistics.pstdev([o.score for o in outs]) if len(outs) > 1 else 0.0
    base_conf = sum(o.confidence * weights[o.name] for o in outs) / wsum
    confidence = max(0.0, min(1.0, base_conf - spread / 100.0))
    bear = sum(1 for o in outs if o.direction == "bearish")
    direction = "bearish" if bear > len(outs) / 2 else ("bullish" if bear == 0 else "neutral")
    return MethodOutput(name="+".join(names), score=round(score, 1), direction=direction,
                        confidence=round(confidence, 3),
                        detail={"members": [o.__dict__ for o in outs], "score_spread": round(spread, 2)})


# --------------------------------------------------------------------------- #
# Built-in methods (wire the bodies in Phase 6 against real bundles)
# --------------------------------------------------------------------------- #
@register("crs_v1")
def _crs_v1(evidence: dict) -> MethodOutput:
    """The fragility×trigger composite from scoring.py (the default)."""
    from . import scoring
    nbf = evidence["normalized_by_factor"]
    r = scoring.compute_crs(nbf, evidence.get("freshness", 1.0), evidence.get("coverage", 1.0))
    direction = "bearish" if r.crs >= 55 else ("neutral" if r.crs >= 35 else "bullish")
    return MethodOutput("crs_v1", r.crs, direction, r.confidence, {"factors": r.factors, "F": r.fragility, "T": r.trigger})


@register("sentiment_analog")
def _sentiment_analog(evidence: dict) -> MethodOutput:
    """Historical-crash resemblance -> mapped to a 0..100 'how close to a known top' score."""
    from .sentiment_analog import assess
    a = assess(**evidence["analog_inputs"])
    # closer to peak (small days_before) => higher score; map 180d->0, 0d->100
    score = max(0.0, min(100.0, 100.0 * (180 - a.est_days_before) / 180.0))
    direction = "bearish" if score >= 55 else "neutral"
    return MethodOutput("sentiment_analog", round(score, 1), direction, a.confidence,
                        {"nearest": a.nearest_event, "days_before": a.est_days_before, "band": a.band_days})


@register("breadth_momentum")
def _breadth_momentum(evidence: dict) -> MethodOutput:
    """Pure-internals method: distribution detection from breadth + phase classifier, no valuation."""
    b = evidence.get("breadth", {})
    div = b.get("index_breadth_divergence", 0.0) or 0.0
    score = max(0.0, min(100.0, 40 + 60 * div))
    direction = "bearish" if div > 0.5 else "neutral"
    return MethodOutput("breadth_momentum", round(score, 1), direction, 0.55, {"divergence": div})


if __name__ == "__main__":
    print("registered methods:", available())
