"""Compact agent chat — trading engine tone, minimal context, short replies.

Hard gate: live LLM only when Supabase auth is configured AND user is on a paid tier.
Without Supabase → demo-safe stub (keyword gate + desk snapshot only).
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from ..db.supabase_client import is_configured
from .agent_gate import gate_message

_COMPACT = Path(__file__).resolve().parents[2] / "agents" / "trading_engine_compact.md"
_MAX_CONTEXT_CHARS = 1200
_MAX_REPLY_TOKENS = 320
_PAID_TIERS = frozenset({"report", "briefing", "agent"})

_STUB_REPLY = (
    "Demo mode: full agent chat ships after account sign-in (Pro or API tier). "
    "I can still help with the desk snapshot below. "
    "Ask about CRS band, fragility vs trigger, or a watchlist ticker."
)


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


def _demo_stub(gate_score: float, *, extra: str = "") -> dict:
    snap = _score_context()
    return {
        "allowed": True,
        "score": gate_score,
        "reason": "demo_stub",
        "auth_configured": False,
        "live_chat": False,
        "reply": f"{_STUB_REPLY}{extra} Desk snapshot: {snap}.",
    }


def chat(message: str, *, tier: str = "free") -> dict:
    gate = gate_message(message)
    if not gate.allowed:
        return {
            "allowed": False,
            "score": gate.score,
            "reason": gate.reason,
            "auth_configured": is_configured(),
            "live_chat": False,
            "reply": gate.response or "Blocked.",
        }

    auth_live = is_configured()
    if not auth_live:
        return _demo_stub(gate.score)

    if tier not in _PAID_TIERS:
        return {
            "allowed": False,
            "score": gate.score,
            "reason": "tier_gated",
            "auth_configured": True,
            "live_chat": False,
            "reply": (
                "Agent chat requires a Pro Desk or API subscription. "
                f"Desk snapshot (read-only): {_score_context()}."
            ),
        }

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return _demo_stub(
            gate.score,
            extra=" Live LLM key not set on server.",
        )

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
    return {
        "allowed": True,
        "score": gate.score,
        "reason": "ok",
        "auth_configured": True,
        "live_chat": True,
        "reply": reply,
    }
