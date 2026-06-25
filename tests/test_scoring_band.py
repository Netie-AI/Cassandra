"""Low coverage must widen confidence band (Claude Phase 4 gate)."""
from src.scoring import confidence_band, compute_crs


def _full_normalized():
    return {
        f: {f"m{i}": 0.7 for i in range(3)}
        for f in "LVSB"
    }


def test_low_coverage_widens_band():
    full = _full_normalized()
    high = compute_crs(full, freshness=1.0, coverage=1.0)
    low = compute_crs(full, freshness=1.0, coverage=0.3)
    assert low.band_halfwidth > high.band_halfwidth


def test_confidence_band_direct():
    factors = [0.7, 0.72, 0.68, 0.71, 0.69]
    _, band_full = confidence_band(1.0, factors, 1.0)
    _, band_low = confidence_band(1.0, factors, 0.3)
    assert band_low > band_full
