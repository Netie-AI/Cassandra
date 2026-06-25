"""Compact agent chat — trading engine tone, minimal context, short replies."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .agent_gate import gate_message

_COMPACT = Path(__file__).resolve().parents[2] / "agents" / "trading_engine_compact.md"
_MAX_CONTEXT_CHARS = 1200
_MAX_REPLY_TOKENS = 320


def _load_persona() -> str:
    if _COMPACT.exists():
        return _COMPACT.read_text(encoding="utf-8")[:_MAX_CONTEXT_CHARS]
    return "Decision-support market desk. No crash dates. No trade execution."


def _score_context() -> str:
    from src.store import latest_score

    s = latest_score()
    if not s:
        return '{"note":"no score yet — run pipeline"}'
    return (
        f'{{"asof":"{s.get("asof")}","crs":{s.get("crs")},'
        f'"band":"{s.get("band")}","fragility":{s.get("fragility")},'
        f'"trigger":{s.get("trigger")},"phase":"{s.get("phase")}",'
        f'"coverage":{s.get("coverage")}}}'
    )


def chat(message: str, *, tier: str = "free") -> dict:
    gate = gate_message(message)
    if not gate.allowed:
        return {
            "allowed": False,
            "score": gate.score,
            "reason": gate.reason,
            "reply": gate.response or "Blocked.",
        }

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "allowed": True,
            "score": gate.score,
            "reason": "offline_stub",
            "reply": (
                "Gate passed. Live chat needs OPENROUTER_API_KEY. "
                f"Desk snapshot: {_score_context()}. "
                "Ask about CRS band, fragility vs trigger, or a watchlist ticker."
            ),
        }

    model = os.getenv("OPENROUTER_AGENT_MODEL", "anthropic/claude-sonnet-4-6")
    system = (
        _load_persona()
        + "\n\nDesk score JSON (cite only these numbers):\n"
        + _score_context()
        + f"\nUser tier: {tier}. Reply in ≤180 words."
    )
    body = {
        "model": model,
        "max_tokens": _MAX_REPLY_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": message.strip()[:2000]},
        ],
    }
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    reply = data["choices"][0]["message"]["content"].strip()
    return {"allowed": True, "score": gate.score, "reason": "ok", "reply": reply}
