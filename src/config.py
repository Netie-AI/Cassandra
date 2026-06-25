"""
src/config.py — config loader. Reads settings.yaml and exposes weights in the shape
scoring.compute_crs() expects. Falls back to module-level defaults if the file is missing.

Usage:
    from src.config import load_weights
    weights = load_weights()          # None if settings.yaml absent → scoring uses defaults
    result = scoring.compute_crs(nbf, weights=weights)

Run standalone: python -m src.config   (prints the loaded weight dict)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .tools._env import load_env

load_env()
ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CFG = ROOT / "config" / "settings.yaml"


def load_weights(path: Path | None = None) -> Optional[dict]:
    """
    Returns a weights dict {'intra': {...}, 'factor': {...}, 'crs': {...}} or None.
    Returns None (not an empty dict) when the file is absent so the caller can
    distinguish "no config" from "config with some keys missing."
    """
    try:
        import yaml
    except ImportError:
        return None

    p = path or _DEFAULT_CFG
    if not p.exists():
        return None

    try:
        cfg = yaml.safe_load(p.read_text()) or {}
    except Exception:
        return None

    intra = cfg.get("intra_weights") or {}
    factor = cfg.get("factor_weights") or {}
    crs = cfg.get("crs_weights") or {}

    # Validate that any weights present sum to 1 (within tolerance)
    def _check_sum(d: dict, name: str) -> None:
        if not d:
            return
        total = sum(d.values())
        if abs(total - 1.0) > 0.02:
            import warnings
            warnings.warn(f"config: {name} weights sum to {total:.3f}, expected 1.0", stacklevel=3)

    _check_sum(factor, "factor_weights")
    _check_sum(crs, "crs_weights")
    for fname, fd in intra.items():
        _check_sum(fd, f"intra_weights.{fname}")

    return {"intra": intra, "factor": factor, "crs": crs}


def load_settings(path: Path | None = None) -> dict:
    """Full settings dict — weights + basket + schedule + feature flags."""
    try:
        import yaml
    except ImportError:
        return {}
    p = path or _DEFAULT_CFG
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


if __name__ == "__main__":
    import json
    w = load_weights()
    if w is None:
        print("No settings.yaml found — scoring.py will use module-level defaults (weights unchanged)")
    else:
        print("Loaded weights from settings.yaml:")
        print(json.dumps(w, indent=2))
        # Verify the worked example still produces 56.9 with these weights
        from src import scoring
        r = scoring._worked_example(weights=w)
        print(f"\nWorked example with config weights: CRS={r.crs} (expected 56.9)")
        assert abs(r.crs - 56.9) < 0.1, f"config weights changed CRS: got {r.crs}"
        print("Gate: OK CRS unchanged with config weights")
