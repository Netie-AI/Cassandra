"""Self-test of the WeLink step engine against a LOCAL MOCK page (tests/fixtures/welink_mock.html).

Runs the real Python Playwright + a real Chromium. This proves the engine only, NOT anything about real WeLink.
Browser location: env WELINK_SELFTEST_CHROME (default /opt/pw-browsers/chromium-1243/chrome-linux64/chrome), run with
--no-sandbox. Usage: python scripts/welink_selftest.py
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.briefing import welink  # noqa: E402

CHROME = os.environ.get("WELINK_SELFTEST_CHROME", "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
MOCK = (ROOT / "tests" / "fixtures" / "welink_mock.html").resolve().as_uri()
MESSAGE = "Morning briefing\nLine two: markets up 1.2%\nLine three: end"
failures = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}{' (' + extra + ')' if extra and not cond else ''}")
    if not cond:
        failures.append(name)


def config(tmp: Path, chat: str) -> dict:
    return {
        "targets": {"ai": [{"name": "mock-ai", "transport": "browser", "chat": chat}]},
        "limits": {"min_interval_s": 0},
        "ledger": str(tmp / "sent.json"),
        "screenshot_dir": str(tmp / "shots"),
        "browser": {
            "url": MOCK, "profile_dir": str(tmp / "profile"), "executable_path": CHROME, "args": ["--no-sandbox"],
            "headless": True, "ready": "#me", "timeouts": {"step_ms": 1500, "ready_ms": 5000},
            "sent_check": {"selector": '#conversation .msg:has-text("{line}")', "timeout_ms": 3000},
            "steps": [
                {"action": "click", "selector": "#search"},
                {"action": "fill", "selector": "#search", "value": "{chat}"},
                {"action": "click", "selector": 'li.chat:has-text("{chat}")'},
                {"action": "insert_text", "selector": "#editor", "value": "{message}"},
                {"action": "press", "key": "Enter", "selector": "#editor", "final": True},
            ],
        },
    }


def main() -> int:
    opened, texts = [], []
    orig = welink._browser_session

    @contextlib.contextmanager
    def spy(bcfg, headless=None):
        opened.append(1)
        with orig(bcfg, headless) as page:
            yield page
            texts.extend(page.locator("#conversation .msg").all_inner_texts())   # read before the browser closes

    welink._browser_session = spy
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        batches = [{"channel": "ai", "messages": [MESSAGE]}]
        out = welink.deliver(batches, config(tmp, "Mock Alpha"), dry_run=False, log=lambda s: print("  |", s))
        check("first run sends 1 message", (out["sent"], out["failed"]) == (1, 0), str(out))
        check("message appears in the conversation with its line breaks", texts == [MESSAGE], repr(texts))
        check("ledger file written", (tmp / "sent.json").is_file())

        n = len(opened)
        out = welink.deliver(batches, config(tmp, "Mock Alpha"), dry_run=False, log=lambda s: print("  |", s))
        check("second run is skipped by the ledger", (out["sent"], out["skipped"], out["failed"]) == (0, 1, 0), str(out))
        check("second run did not open a browser", len(opened) == n)

        out = welink.deliver([{"channel": "ai", "messages": ["other text"]}], config(tmp, "No Such Chat"),
                             dry_run=False, log=lambda s: print("  |", s))
        shots = list((tmp / "shots").glob("fail-*.png"))
        check("missing chat is a failure with a screenshot", out["failed"] == 1 and len(shots) == 1, str(out))
        check("failed send not in ledger", welink._key("mock-ai", "other text") not in welink._ledger_load(tmp / "sent.json"))
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
