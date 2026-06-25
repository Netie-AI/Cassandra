"""Tier lookup stub — Supabase JWT wiring in PARKING_LOT.md."""
from __future__ import annotations

from fastapi import Header

VALID_TIERS = frozenset({"free", "report", "briefing", "agent"})
LOCKED_FACTORS = ("S", "B", "C")


def get_user_tier(
    authorization: str | None = Header(default=None),
    x_tier: str | None = Header(default=None, alias="X-Tier"),
) -> str:
    """Return user tier. Dev: pass X-Tier header. Prod: Supabase JWT (parking lot)."""
    if x_tier and x_tier.lower() in VALID_TIERS:
        return x_tier.lower()
    if authorization and authorization.startswith("Bearer "):
        # TODO: decode Supabase JWT → tier claim
        pass
    return "free"


def gate_score(score: dict | None, tier: str) -> dict | None:
    if not score:
        return score
    if tier in ("report", "briefing", "agent"):
        return score
    out = dict(score)
    factors = dict(out.get("factors") or {})
    for key in LOCKED_FACTORS:
        if key in factors:
            factors[key] = None
    out["factors"] = factors
    return out
