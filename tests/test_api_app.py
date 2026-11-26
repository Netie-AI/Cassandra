"""The API starts, guards /api/*, and serves the score and briefing routes from real data paths."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.middleware import ip_guard


def test_app_imports():
    import api.main  # noqa: F401  (failed before api/middleware was committed)


@pytest.fixture(autouse=True)
def _clean_guard(monkeypatch):
    monkeypatch.delenv("IP_DENYLIST", raising=False)
    monkeypatch.delenv("IP_ALLOWLIST", raising=False)
    ip_guard.reset()
    yield
    ip_guard.reset()


def test_ip_guard_denylist_cidr(monkeypatch):
    monkeypatch.setenv("IP_DENYLIST", "203.0.113.0/24, not-an-ip")
    assert ip_guard.check_ip("203.0.113.9", "api_default") == (False, "ip_denied")
    assert ip_guard.check_ip("198.51.100.1", "api_default") == (True, "ok")


def test_ip_guard_budget_then_block(monkeypatch):
    monkeypatch.setitem(ip_guard.BUDGETS, "auth_attempt", (2, 60))
    t = 1000.0
    assert ip_guard.check_ip("192.0.2.1", "auth_attempt", now=t)[0]
    assert ip_guard.check_ip("192.0.2.1", "auth_attempt", now=t)[0]
    assert ip_guard.check_ip("192.0.2.1", "auth_attempt", now=t) == (False, "too_many_auth_attempt")
    assert ip_guard.check_ip("192.0.2.2", "auth_attempt", now=t)[0]            # other IPs unaffected
    assert ip_guard.check_ip("192.0.2.1", "auth_attempt", now=t + 61)[0]       # window slides
    for _ in range(ip_guard.STRIKES_TO_BLOCK):
        ip_guard.check_ip("192.0.2.1", "auth_attempt", now=t + 61)
    assert ip_guard.check_ip("192.0.2.1", "api_default", now=t + 62) == (False, "ip_blocked")
    assert ip_guard.check_ip("192.0.2.1", "api_default", now=t + 62 + ip_guard.BLOCK_S)[0]


def test_ip_guard_allowlist_skips_budget(monkeypatch):
    monkeypatch.setenv("IP_ALLOWLIST", "10.0.0.0/8")
    monkeypatch.setitem(ip_guard.BUDGETS, "api_default", (1, 60))
    assert all(ip_guard.check_ip("10.1.2.3", "api_default", now=5.0)[0] for _ in range(5))


def test_log_ip_event_records_refusals_only():
    ip_guard.log_ip_event("192.0.2.5", "api_default", True, "ok")
    ip_guard.log_ip_event("192.0.2.5", "api_default", False, "ip_denied")
    ev = ip_guard.recent_events()
    assert len(ev) == 1 and ev[0]["reason"] == "ip_denied"


def test_denied_ip_gets_429_from_api(monkeypatch):
    from api.main import app

    monkeypatch.setenv("IP_DENYLIST", "0.0.0.0/0")
    monkeypatch.setattr(ip_guard, "_in", lambda ip, nets: bool(nets))   # TestClient host is "testclient"
    r = TestClient(app).get("/api/geo")
    assert r.status_code == 429 and r.json()["error"] == "ip_denied"


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    from src import store

    monkeypatch.setattr(store, "DB", tmp_path / "scores.sqlite")
    return store


def _row(asof, crs):
    return {"asof": asof, "crs": crs, "band": "Awareness", "band_halfwidth": 2.0, "confidence": 0.8,
            "fragility": 0.5, "trigger": 0.4, "coverage": 0.25, "factors_json": "{}",
            "momentum_state": "plateau", "df_dt": 0.0, "phase": "accumulation", "phase_confidence": 0.4,
            "payload_json": "{}"}


def test_snapshot_round_trip_and_seed_only_when_empty(tmp_store, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"version": 1, "rows": [_row("2026-11-25", 40.0), _row("2026-11-26", 41.0)]}))
    assert tmp_store.seed_scores_if_empty(seed) == 2
    assert tmp_store.latest_score()["crs"] == 41.0
    assert tmp_store.seed_scores_if_empty(seed) == 0                  # never overwrites real runs
    out = tmp_path / "out.json"
    assert tmp_store.export_score_snapshot(out) == 2
    assert [r["asof"] for r in json.loads(out.read_text())["rows"]] == ["2026-11-25", "2026-11-26"]
    assert tmp_store.import_score_snapshot(tmp_path / "missing.json") == 0


def test_committed_seed_is_a_real_pipeline_row():
    from src.store import SEED

    rows = json.loads(SEED.read_text())["rows"]
    assert rows and all(0 <= r["crs"] <= 100 and 0 < r["coverage"] <= 1 for r in rows)


def test_latest_and_dashboard_serve_seeded_score(tmp_store, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"version": 1, "rows": [_row("2026-11-26", 41.0)]}))
    tmp_store.seed_scores_if_empty(seed)
    from api.main import app

    c = TestClient(app)
    latest = c.get("/api/latest")
    assert latest.status_code == 200 and latest.json()["coverage"] == 0.25
    assert c.get("/api/dashboard").status_code == 200
    hist = c.get("/api/scores/history?limit=5").json()["history"]
    assert hist[0]["asof"] == "2026-11-26"


def test_briefing_route_falls_back(tmp_path, monkeypatch):
    import api.main as m

    monkeypatch.setattr(m, "ROOT", tmp_path)
    c = TestClient(m.app)
    r = c.get("/briefing")
    assert r.status_code == 200 and "No edition has been built" in r.text
    folder = tmp_path / "reports" / "briefings"
    folder.mkdir(parents=True)
    (folder / "2026-11-26-morning.html").write_text("<p>morning edition</p>")
    (folder / "2026-11-26-morning-ai.html").write_text("<p>channel only</p>")
    assert "morning edition" in c.get("/briefing").text
    (folder / "latest.html").write_text("<p>latest</p>")
    assert "latest" in c.get("/briefing").text


def test_quote_route_never_500(monkeypatch):
    from api.main import app
    from src.tools import movers

    monkeypatch.setattr(movers, "verified_quote", lambda s: None)
    assert TestClient(app).get("/api/quote/MU").status_code == 404
    monkeypatch.setattr(movers, "verified_quote",
                        lambda s: {"symbol": s, "price": 1.0, "pct_change": 0.5, "source": "yahoo",
                                   "as_of": "2026-11-25", "market_status": "closed"})
    assert TestClient(app).get("/api/quote/MU").json()["source"] == "yahoo"


def test_verified_quote_rejects_bad_symbols_without_network():
    from src.tools.movers import verified_quote

    assert verified_quote("../etc") is None and verified_quote("") is None
