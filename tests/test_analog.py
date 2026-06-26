from src.analog import cosine_match


def test_cosine_match_dot_com_peak():
    key, sim = cosine_match(87, 0.91, 0.83)
    assert key == "dot-com-2000"
    assert sim > 0.99


def test_cosine_match_weak_returns_none():
    # Directionally unlike peak regimes — must not claim an analog below threshold.
    key, sim = cosine_match(50, 0.10, 0.10)
    assert key is None
    assert sim < 0.82
