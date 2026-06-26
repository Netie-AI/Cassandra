"""Cassandra cycle-adjusted price target — pure Python, no LLM math."""
from __future__ import annotations


def compute_cassandra_target(
    morningstar_fv: float,
    crs: float,
    capex_score: float,
) -> dict:
    """
    Phase multiplier:
    CRS < 30 (Stable/Complacent): 1.15  — ride the wave
    CRS 30-50 (Aware):            1.00  — hold
    CRS 50-70 (Distribution):     0.85  — trim
    CRS > 70 (Mania/Danger):      0.65  — short candidate / exit

    Capex adjustment: if capex_score > 0.80 (FIRE): multiply by 0.80 additional
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
        "methodology": f"MF={morningstar_fv} × phase({phase_mult}) × capex({capex_mult})",
    }


def capex_score_from_score_dict(score: dict | None) -> float:
    """Pull capex-cut NLP signal from latest daily score payload when present."""
    if not score:
        return 0.0
    payload = score.get("payload_json") or score.get("payload") or {}
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    factors = score.get("factors") or {}
    if isinstance(factors, str):
        import json

        try:
            factors = json.loads(factors)
        except json.JSONDecodeError:
            factors = {}
    c_factor = factors.get("C") if isinstance(factors, dict) else None
    if isinstance(c_factor, dict):
        raw = c_factor.get("capex_cut_nlp")
        if raw is not None:
            return float(raw)
    raw = payload.get("capex_cut_nlp") if isinstance(payload, dict) else None
    return float(raw) if raw is not None else 0.0
