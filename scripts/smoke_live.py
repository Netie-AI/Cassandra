"""
Live smoke against deployed crash.netie.ai (or SMOKE_LIVE_URL).

Usage:
  python scripts/smoke_live.py
  SMOKE_LIVE_URL=https://crash.netie.ai python scripts/smoke_live.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = os.getenv("SMOKE_LIVE_URL", "https://crash.netie.ai")
ERRORS: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        print(f"  [OK] {label}")
    except Exception as exc:
        print(f"  [FAIL] {label}: {exc}")
        ERRORS.append(label)


def main() -> int:
    from src.tools._env import load_env

    load_env()
    print(f"CASSANDRA live smoke - {BASE}\n")

    check("Health", lambda: _assert_health())
    check("Diagnostics crs_last", lambda: _assert_diagnostics())
    check("Newspaper page", lambda: _assert_newspaper())
    check("Privacy page", lambda: _assert_static("/privacy", "Privacy Policy"))
    check("Terms page", lambda: _assert_static("/terms", "Terms of Service"))

    print(f"\n{'ALL CLEAR' if not ERRORS else f'FAILED: {ERRORS}'}")
    return 0 if not ERRORS else 1


def _assert_health() -> None:
    r = httpx.get(f"{BASE}/api/health", timeout=20.0, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    assert data.get("status") == "ok", data


def _assert_diagnostics() -> None:
    r = httpx.get(f"{BASE}/api/diagnostics", timeout=20.0, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    assert "crs_last" in data, data
    assert data.get("crs_last") is not None, "crs_last is null — run pipeline on laptop"


def _assert_newspaper() -> None:
    r = httpx.get(f"{BASE}/newspaper-report", timeout=20.0, follow_redirects=True)
    r.raise_for_status()
    text = r.text
    assert "subscribe-overlay" in text or "Cassandra" in text


def _assert_static(path: str, needle: str) -> None:
    r = httpx.get(f"{BASE}{path}", timeout=20.0, follow_redirects=True)
    r.raise_for_status()
    assert needle in r.text


if __name__ == "__main__":
    sys.exit(main())
