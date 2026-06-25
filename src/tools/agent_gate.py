"""Local fuzzy keyword gate for agent chat — blocks off-topic / prompt-injection attempts."""
from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_KEYWORDS = frozenset({
    "stock", "stocks", "market", "risk", "capex", "earnings", "price", "index",
    "options", "volatility", "sector", "signal", "crs", "fragility", "trigger",
    "wyckoff", "analog", "sentiment", "fed", "rate", "yield", "breadth", "vix",
    "semiconductor", "semis", "tech", "nasdaq", "spx", "ndx", "macro", "gdp",
    "inflation", "recession", "drawdown", "support", "resistance", "guidance",
    "hyperscaler", "memory", "dram", "hbm", "flow", "put", "call", "gamma",
    "portfolio", "watchlist", "ticker", "equity", "bond", "credit", "spread",
})

BLOCKED_PATTERNS = [
    re.compile(p, re.I) for p in (
        r"\bapi\s*key",
        r"\bsystem\s*prompt",
        r"\bignore\s+(all\s+)?previous",
        r"\bshow\s+me\s+your",
        r"\bwhat\s+are\s+your\s+instructions",
        r"\breveal\s+(your\s+)?prompt",
        r"\bjailbreak",
        r"\bDAN\s+mode",
        r"\bpretend\s+you\s+are",
        r"\bpassword",
        r"\bsecret\s+key",
    )
]

CANNED_LOW_RELEVANCE = (
    "I only answer market-structure and risk questions grounded in today's Cassandra desk data. "
    "Try asking about CRS, fragility, triggers, a ticker on your watchlist, or sector volatility."
)

CANNED_BLOCKED = (
    "That request can't be processed. Ask a specific market or risk question instead."
)


@dataclass
class GateResult:
    allowed: bool
    score: float
    reason: str
    response: str | None = None


def score_message(text: str) -> float:
    """Relevance score 0–1 from keyword overlap + length heuristic."""
    if not text or not text.strip():
        return 0.0
    lower = text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lower))
    if not tokens:
        return 0.0
    hits = sum(1 for kw in ALLOWED_KEYWORDS if kw in lower or kw in tokens)
    # partial token match (e.g. "semiconductor" contains no exact kw but "semi" won't match — ok)
    density = hits / max(len(tokens), 1)
    base = min(1.0, hits * 0.18 + density * 0.35)
    if hits >= 2:
        base = min(1.0, base + 0.25)
    if len(text.strip()) < 8:
        base *= 0.6
    return round(base, 3)


def gate_message(text: str, *, threshold: float = 0.4) -> GateResult:
    """Return gate decision. Blocked/injection → canned response, no LLM."""
    cleaned = (text or "").strip()
    for pat in BLOCKED_PATTERNS:
        if pat.search(cleaned):
            return GateResult(
                allowed=False,
                score=0.0,
                reason="blocked_pattern",
                response=CANNED_BLOCKED,
            )
    rel = score_message(cleaned)
    if rel < threshold:
        return GateResult(
            allowed=False,
            score=rel,
            reason="low_relevance",
            response=CANNED_LOW_RELEVANCE,
        )
    return GateResult(allowed=True, score=rel, reason="ok", response=None)
