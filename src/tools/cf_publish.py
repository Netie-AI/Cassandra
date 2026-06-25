"""Publish latest DailyScore to Cloudflare KV via Worker (read-only public dashboard)."""
from __future__ import annotations

import os

import httpx

from ..schemas import DailyScore


def publish_score(score: DailyScore) -> None:
    endpoint = os.getenv("CF_KV_ENDPOINT")
    secret = os.getenv("CF_KV_SECRET")
    if not endpoint or not secret:
        return

    payload = {
        "crs": score.crs,
        "band": score.band_label,
        "fragility": score.fragility,
        "trigger": score.trigger,
        "phase": score.phase.value,
        "phase_confidence": score.phase_confidence,
        "coverage": score.coverage,
        "asof": score.asof.isoformat(),
    }
    httpx.put(
        endpoint,
        json=payload,
        headers={"X-Secret": secret},
        timeout=10,
    )
