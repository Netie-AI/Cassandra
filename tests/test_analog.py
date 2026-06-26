from src.analog import cosine_match


def test_cosine_match_dot_com_peak():
    key, sim = cosine_match(87, 0.91, 0.83)
    assert key == "dot-com-2000"
    assert sim > 0.99
