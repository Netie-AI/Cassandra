"""In-memory per-IP rate limiting for public API routes."""
from __future__ import annotations

import time
from collections import defaultdict

_hits: dict[str, list[float]] = defaultdict(list)

LIMITS = {
    "/api/agent/chat": (5, 60),
    "/api/digest/signup": (3, 300),
    "/api/newsletter/dispatch": (1, 3600),
    "default": (60, 60),
}


def check(path: str, ip: str) -> bool:
    """Returns True if allowed, False if rate limited."""
    limit, window = LIMITS.get(path, LIMITS["default"])
    now = time.time()
    bucket = f"{ip}:{path}"
    _hits[bucket] = [t for t in _hits[bucket] if now - t < window]
    if len(_hits[bucket]) >= limit:
        return False
    _hits[bucket].append(now)
    return True
