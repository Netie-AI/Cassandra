"""Per-IP guard for /api/* routes, used by api/main.py before the per-route rate limiter.

check_ip(ip, action) -> (allowed, reason)
    1. IP_DENYLIST (comma-separated IPs or CIDRs) is always refused: reason "ip_denied".
    2. IP_ALLOWLIST, when set, is never throttled here (ops boxes, uptime checks).
    3. Each action has a sliding-window budget per IP. Going over it refuses the call
       ("too_many_<action>") and records a strike; STRIKES_TO_BLOCK strikes inside
       STRIKE_WINDOW_S block that IP for BLOCK_S seconds ("ip_blocked").

log_ip_event(ip, action, allowed, reason) logs refusals only (allowed calls are not logged, to keep
the log small) and keeps the last 500 refusals in memory for the ops page (recent_events()).

State is in-process memory: it resets on restart and is per worker, which is enough for one
uvicorn process. A multi-instance deploy should put a shared limiter (Cloudflare rate limiting
rule or Redis) in front; this guard stays as the last line.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
from collections import defaultdict, deque

_LOG = logging.getLogger("cassandra.ip_guard")

# action -> (max calls, window seconds). Budgets sit above the per-route limits in
# api/rate_limit.py, so this guard only catches sustained abuse across routes.
BUDGETS: dict[str, tuple[int, int]] = {
    "api_default": (300, 60),
    "auth_attempt": (20, 300),
    "agent_generate": (30, 3600),
}
STRIKES_TO_BLOCK = 5
STRIKE_WINDOW_S = 600
BLOCK_S = 900

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_strikes: dict[str, deque] = defaultdict(deque)
_blocked_until: dict[str, float] = {}
_events: deque = deque(maxlen=500)


def _networks(var: str) -> list[ipaddress._BaseNetwork]:
    out = []
    for part in (os.getenv(var) or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            _LOG.warning("%s: ignoring invalid entry %r", var, part)
    return out


def _in(ip: str, nets: list) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr.version == n.version and addr in n for n in nets)


def check_ip(ip: str, action: str = "api_default", *, now: float | None = None) -> tuple[bool, str]:
    now = time.time() if now is None else now
    if _in(ip, _networks("IP_DENYLIST")):
        return False, "ip_denied"
    if _in(ip, _networks("IP_ALLOWLIST")):
        return True, "allowlisted"
    limit, window = BUDGETS.get(action, BUDGETS["api_default"])
    with _lock:
        until = _blocked_until.get(ip)
        if until and until > now:
            return False, "ip_blocked"
        if until:
            _blocked_until.pop(ip, None)
        q = _hits[(ip, action)]
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= limit:
            s = _strikes[ip]
            while s and now - s[0] >= STRIKE_WINDOW_S:
                s.popleft()
            s.append(now)
            if len(s) >= STRIKES_TO_BLOCK:
                _blocked_until[ip] = now + BLOCK_S
                s.clear()
                return False, "ip_blocked"
            return False, f"too_many_{action}"
        q.append(now)
    return True, "ok"


def log_ip_event(ip: str, action: str, allowed: bool, reason: str) -> None:
    if allowed:
        return
    _events.append({"ts": time.time(), "ip": ip, "action": action, "reason": reason})
    _LOG.warning("ip_guard refused ip=%s action=%s reason=%s", ip, action, reason)


def recent_events(limit: int = 50) -> list[dict]:
    return list(_events)[-limit:]


def reset() -> None:
    """Clear all state (tests)."""
    with _lock:
        _hits.clear()
        _strikes.clear()
        _blocked_until.clear()
        _events.clear()
