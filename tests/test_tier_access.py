"""Tier access + highlights API tests."""
from api.auth import FREE_DELAY_DAYS, gate_score, is_paid, resolve_score_dict


def test_is_paid():
    assert is_paid("report")
    assert is_paid("master")
    assert not is_paid("free")


def test_gate_score_master_unlocked():
    raw = {"crs": 40, "factors": {"L": 0.5, "S": 0.7, "B": 0.6, "C": 0.5}}
    out = gate_score(raw, "master")
    assert out["factors"]["S"] == 0.7


def test_gate_score_locks_sbc_for_free():
    raw = {"crs": 40, "factors": {"L": 0.5, "S": 0.7, "B": 0.6, "C": 0.5}}
    out = gate_score(raw, "free")
    assert out["factors"]["S"] is None
    assert out["factors"]["L"] == 0.5


def test_free_delay_constant():
    assert FREE_DELAY_DAYS == 2
