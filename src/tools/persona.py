"""Load Cassandra investor persona for LLM system prompts."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PERSONA = _ROOT / "agents" / "cassandra_investor_persona.md"
_DEFAULT_MAX = 900


def load_cassandra_persona(*, max_chars: int = _DEFAULT_MAX) -> str:
    if _PERSONA.exists():
        return _PERSONA.read_text(encoding="utf-8")[:max_chars]
    return "Cassandra investment analyst. Decision-support only. No crash dates."
