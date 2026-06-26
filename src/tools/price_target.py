"""Cassandra cycle-adjusted price target — pure Python, no LLM math."""
from __future__ import annotations

import json


def compute_cassandra_target(
    morningstar_fv: float,
    crs: float,
    capex_score: float,
) -> dict:
    """
    Phase multiplier:
    CRS < 30 (Stable/Complacent): 1.15  — ride the wave
    CRS 30-49 (Aware):            1.00  — hold
    CRS 50-69 (Distribution):     0.85  — trim
    CRS >= 70 (Mania/Danger):       0.65  — short candidate / exit

    Capex adjustment: if capex_score >= 0.80 (FIRE): multiply by 0.80 additional
    """
    if crs < 30:
        phase_mult = 1.15
    elif crs < 50:
        phase_mult = 1.00
    elif crs < 70:
        phase_mult = 0.85
    else:
        phase_mult = 0.65

    capex_mult = 0.80 if capex_score >= 0.80 else 1.0
    target = morningstar_fv * phase_mult * capex_mult

    if phase_mult >= 1.0:
        stance = "Long"
    elif phase_mult > 0.70:
        stance = "Reduce"
    else:
        stance = "Short watch"

    return {
        "target": round(target, 2),
        "stance": stance,
        "phase_mult": phase_mult,
        "capex_mult": capex_mult,
        "methodology": f"MF={morningstar_fv} x phase({phase_mult}) x capex({capex_mult})",
    }


def _as_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def capex_score_from_score_dict(score: dict | None) -> float:
    """Pull capex-cut NLP signal from latest daily score payload when present."""
    if not score:
        return 0.0
    extra = _as_dict(score.get("extra"))
    raw = extra.get("capex_cut_nlp")
    if raw is None:
        orch = _as_dict(extra.get("orchestrator"))
        raw = orch.get("capex_cut_nlp")
    if raw is not None:
        return float(raw)
    payload = _as_dict(score.get("payload_json") or score.get("payload"))
    raw = payload.get("capex_cut_nlp")
    return float(raw) if raw is not None else 0.0
