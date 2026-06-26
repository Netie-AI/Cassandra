"""Historical regime corpus + cosine similarity (descriptive only)."""
from __future__ import annotations

import math

CORPUS = {
    "dot-com-2000": {
        "peak_crs": 87,
        "f_at_peak": 0.91,
        "t_at_peak": 0.83,
        "months_to_capitulation": 18,
        "label": "Dot-com peak (Mar 2000)",
    },
    "gfc-2007": {
        "peak_crs": 79,
        "f_at_peak": 0.85,
        "t_at_peak": 0.71,
        "months_to_capitulation": 14,
        "label": "GFC peak (Oct 2007)",
    },
    "2021-22": {
        "peak_crs": 71,
        "f_at_peak": 0.78,
        "t_at_peak": 0.58,
        "months_to_capitulation": 12,
        "label": "Rate-shock peak (Nov 2021)",
    },
}


def cosine_match(crs: float, f: float, t: float) -> tuple[str | None, float]:
    """Return (regime_key, similarity_score 0-1)."""
    vec = [crs / 100, f, t]
    best_key: str | None = None
    best_sim = -1.0
    for key, ref in CORPUS.items():
        r = [ref["peak_crs"] / 100, ref["f_at_peak"], ref["t_at_peak"]]
        dot = sum(a * b for a, b in zip(vec, r))
        mag = math.sqrt(sum(a**2 for a in vec)) * math.sqrt(sum(b**2 for b in r))
        sim = dot / mag if mag else 0.0
        if sim > best_sim:
            best_key, best_sim = key, sim
    return best_key, round(best_sim, 3)
