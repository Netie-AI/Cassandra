"""Rate limit middleware tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api import rate_limit
from api.main import app


def test_agent_chat_sixth_call_returns_429():
    rate_limit._hits.clear()
    client = TestClient(app)
    payload = {"message": "What is CRS fragility vs trigger?"}
    for i in range(5):
        resp = client.post("/api/agent/chat", json=payload)
        assert resp.status_code != 429, f"unexpected 429 on request {i + 1}"
    resp = client.post("/api/agent/chat", json=payload)
    assert resp.status_code == 429
    assert resp.json().get("error") == "rate_limited"
