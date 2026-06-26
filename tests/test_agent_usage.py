from src.store import get_agent_usage, increment_agent_usage


def test_agent_usage_increment(tmp_path, monkeypatch):
    import src.store as store_mod

    monkeypatch.setattr(store_mod, "DB", tmp_path / "test.sqlite")
    assert get_agent_usage("user@example.com", "2026-06-26") == 0
    assert increment_agent_usage("user@example.com", "2026-06-26") == 1
    assert increment_agent_usage("user@example.com", "2026-06-26") == 2
    assert get_agent_usage("user@example.com", "2026-06-26") == 2
    assert get_agent_usage("other@example.com", "2026-06-26") == 0
