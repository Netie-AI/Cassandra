"""Load Cassandra investor persona for LLM system prompts."""
from __future__ import annotations

from pathlib import Path

from .copy_lint import lint_no_em_dash

_ROOT = Path(__file__).resolve().parents[2]
_PERSONA = _ROOT / "agents" / "cassandra_investor_persona.md"
_DEFAULT_MAX = 1600


def load_cassandra_persona(*, max_chars: int = _DEFAULT_MAX) -> str:
    if not _PERSONA.exists():
        return "Cassandra investment analyst. Decision-support only. No crash dates."
    text = lint_no_em_dash(_PERSONA.read_text(encoding="utf-8"))
    return text[:max_chars]
