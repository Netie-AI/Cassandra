"""
Run after filling .env. Tests every configured integration.
Start API first: .\\scripts\\start.ps1
python scripts/smoke_full.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = os.getenv("SMOKE_BASE_URL", "http://localhost:8080")
ERRORS: list[str] = []


def _raise_newsletter_dry_run() -> None:
    code = os.system("python -m src.newsletter.send --dry-run")
    if code != 0:
        raise RuntimeError(f"dry-run exit code {code}")


def assert_ok(resp: httpx.Response) -> None:
    resp.raise_for_status()
    data = resp.json()
    assert data.get("status") == "ok", data


def assert_fields(obj: dict, fields: list[str]) -> None:
    for field in fields:
        assert field in obj, f"missing {field}"


def assert_field(obj: dict, key: str, expected: object) -> None:
    assert obj.get(key) == expected, f"{key}={obj.get(key)!r} expected {expected!r}"


def assert_sim(result: tuple[str | None, float]) -> None:
    key, sim = result
    assert key == "dot-com-2000", key
    assert sim > 0.99, sim


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
    print(f"CASSANDRA smoke - {BASE}\n")

    check("API health", lambda: assert_ok(httpx.get(f"{BASE}/api/health", timeout=10.0)))

    check(
        "Diagnostics",
        lambda: assert_fields(
            httpx.get(f"{BASE}/api/diagnostics", timeout=10.0).json(),
            ["crs_last", "phase_last", "supabase_configured", "finnhub_configured"],
        ),
    )

    check(
        "Agent chat demo",
        lambda: assert_field(
            httpx.post(
                f"{BASE}/api/agent/chat",
                json={"message": "What is CRS?"},
                timeout=15.0,
            ).json(),
            "live_chat",
            False,
        ),
    )

    check(
        "Digest signup",
        lambda: assert_field(
            httpx.post(
                f"{BASE}/api/digest/signup",
                json={"email": "smoke@netie.ai"},
                timeout=10.0,
            ).json(),
            "confirmed",
            True,
        ),
    )

    check(
        "Newsletter dry-run",
        lambda: (_raise_newsletter_dry_run()),
    )

    check("Orchestrator import", lambda: __import__("src.orchestrator"))

    check("Capex NLP import", lambda: __import__("src.tools.capex_nlp"))

    check(
        "Analog cosine (dot-com)",
        lambda: assert_sim(
            __import__("src.analog", fromlist=["cosine_match"]).cosine_match(87, 0.91, 0.83)
        ),
    )

    print(f"\n{'ALL CLEAR' if not ERRORS else f'FAILED: {ERRORS}'}")
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
