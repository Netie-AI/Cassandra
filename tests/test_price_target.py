from src.tools.price_target import compute_cassandra_target


def test_phase_accumulation_ride():
    out = compute_cassandra_target(100.0, crs=20.0, capex_score=0.2)
    assert out["phase_mult"] == 1.15
    assert out["target"] == 115.0
    assert out["stance"] == "Long"


def test_distribution_trim():
    out = compute_cassandra_target(100.0, crs=55.0, capex_score=0.2)
    assert out["phase_mult"] == 0.85
    assert out["target"] == 85.0
    assert out["stance"] == "Reduce"


def test_mania_capex_fire():
    out = compute_cassandra_target(100.0, crs=75.0, capex_score=0.85)
    assert out["phase_mult"] == 0.65
    assert out["capex_mult"] == 0.80
    assert out["target"] == 52.0
    assert out["stance"] == "Short watch"
