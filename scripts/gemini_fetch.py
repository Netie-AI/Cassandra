#!/usr/bin/env python3
"""Fetch Gemini scheduled-action results into inbox/gemini/.

Attaches over CDP to an already signed-in Chrome (GEMINI_CDP_URL, default
http://127.0.0.1:9223). Opens https://gemini.google.com/app. If the page is
accounts.google.com, exits 3 and prints needs-login. This script never types
credentials.

    python scripts/gemini_fetch.py
    python scripts/gemini_fetch.py --dry-run     # row counts only, writes nothing

Live Gemini controls (role and text locators below) are NOT verified against the
current Gemini page. The markdown parser is what the unit tests run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.briefing.gemini_inbox import SG, parse_markdown_response  # noqa: E402

APP_URL = "https://gemini.google.com/app"
DEFAULT_CDP = "http://127.0.0.1:9223"
_ROW_KEYS = ("topic", "headline", "publisher", "published", "link", "sentence")
_SCHEDULED = (re.compile(r"scheduled actions", re.I), re.compile(r"^scheduled$", re.I))


class NeedsLogin(Exception):
    pass


class FetchError(Exception):
    """A failure whose message is safe to print (no page body, no key)."""


def login_wall(url: str) -> bool:
    """True for any page that is not a usable signed-in Gemini page: the Google sign-in host, the
    consent host, and Google's "unusual traffic" interstitial (www.google.com/sorry/...)."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host == "accounts.google.com" or host.endswith(".accounts.google.com"):
        return True
    if host == "consent.google.com":
        return True
    if host.endswith("google.com") and parts.path.startswith("/sorry"):
        return True
    return False


def is_gemini_host(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == "gemini.google.com"


def slugify(title: str) -> str:
    text = title.lower().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "action"


def load_actions(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    titles = []
    for item in data.get("actions") or []:
        if isinstance(item, str) and item.strip():
            titles.append(item.strip())
        elif isinstance(item, dict) and str(item.get("title") or "").strip():
            titles.append(str(item["title"]).strip())
    if not titles:
        raise FetchError("no actions configured")
    return titles


def _row_out(row: dict) -> dict[str, str]:
    return {k: str(row.get(k) or "")[:500] for k in _ROW_KEYS}


def record_result(inbox: Path, title: str, text: str, *, dry_run: bool,
                  now: dt.datetime | None = None) -> int:
    """Write inbox/gemini/<date>-<action>.md and .json. Dry-run writes nothing.
    Returns the row count. Prints only the count when dry_run is set."""
    parsed = parse_markdown_response(text)
    n = len(parsed["rows"])
    if dry_run:
        print(f"{title}: {n} rows")
        return n
    moment = (now or dt.datetime.now(SG)).astimezone(SG)
    inbox.mkdir(parents=True, exist_ok=True)
    stem = f"{moment.date().isoformat()}-{slugify(title)}"
    body = {
        "action": title,
        "fetched_at": moment.isoformat(timespec="seconds"),
        "source_url": APP_URL,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "closing": parsed["closing"],
        "rows": [_row_out(r) for r in parsed["rows"]],
    }
    (inbox / f"{stem}.md").write_text(text, encoding="utf-8")
    (inbox / f"{stem}.json").write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def _signed_in(page) -> bool:
    """The signed-in Gemini shell has a "Google Account: <name>" link in the sidebar. A signed-out
    visit shows a "Sign in" link instead."""
    if page.get_by_role("link", name=re.compile(r"^Google Account", re.I)).count():
        return True
    return False


def _guard(page, *, need_account: bool = False) -> None:
    if login_wall(page.url):
        raise NeedsLogin()
    if need_account and not _signed_in(page):
        raise NeedsLogin()


def _pick_page(ctx):
    """Reuse the founder's open Gemini tab. A brand-new tab is a fresh navigation and Google answers
    it with the unusual-traffic page; a tab already in the app can navigate inside it."""
    for pg in ctx.pages:
        if is_gemini_host(pg.url) or login_wall(pg.url):
            return pg, False
    return ctx.new_page(), True


def _click_first(page, patterns: tuple[re.Pattern, ...] | list[re.Pattern]) -> bool:
    """Click the first role or text match. Never types."""
    for role in ("link", "button", "tab"):
        for pat in patterns:
            loc = page.get_by_role(role, name=pat)
            if loc.count():
                loc.first.click()
                return True
    for pat in patterns:
        loc = page.get_by_text(pat)
        if loc.count():
            loc.first.click()
            return True
    return False


def _open_action(page, title: str) -> None:
    if not _click_first(page, [re.compile(re.escape(title), re.I)]):
        raise FetchError(f"action not found on the Scheduled page: {title}")
    _guard(page)
    # UNVERIFIED: some layouts show a list of runs and need an extra click on the latest one.
    _click_first(page, [re.compile(r"^\s*latest\s*$", re.I)])
    _guard(page)


def _last_response(page) -> str:
    articles = page.get_by_role("article")
    n = articles.count()
    if n:
        return articles.nth(n - 1).inner_text()
    main = page.get_by_role("main")
    if main.count():
        return main.inner_text()
    raise FetchError("no response text")


def _back_to_list(page) -> None:
    if not _click_first(page, _SCHEDULED):
        page.go_back()
    _guard(page)


def _open_scheduled(page) -> None:
    link = page.locator('a[href$="/scheduled"], a[href="scheduled"]')
    if link.count():
        link.first.click()
    elif not _click_first(page, [re.compile(r"^\s*scheduled\s*$", re.I)]):
        raise FetchError("scheduled control not found")
    page.wait_for_url(re.compile(r"/scheduled"), timeout=15000)
    page.wait_for_timeout(1500)


def fetch_all(cdp_url: str, titles: list[str], inbox: Path, *, dry_run: bool) -> list[tuple[str, int]]:
    """Attach to Chrome, read each action, record results. Leaves Chrome and its tab open."""
    from playwright.sync_api import sync_playwright

    counts: list[tuple[str, int]] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
        except Exception:
            raise FetchError("cdp unreachable") from None
        if not browser.contexts:
            raise FetchError("cdp browser has no window")
        page, created = _pick_page(browser.contexts[0])
        try:
            page.set_default_timeout(20000)
            _guard(page)                      # an interstitial or sign-in page already open: stop, no navigation
            if not is_gemini_host(page.url):
                page.goto(APP_URL, wait_until="domcontentloaded")
            _guard(page)
            page.wait_for_timeout(1500)
            _guard(page, need_account=True)
            _open_scheduled(page)
            _guard(page, need_account=True)
            for i, title in enumerate(titles):
                if i:
                    _back_to_list(page)
                _open_action(page, title)
                text = _last_response(page)
                if not (text or "").strip():
                    raise FetchError(f"empty response: {title}")
                n = record_result(inbox, title, text, dry_run=dry_run)
                counts.append((title, n))
        finally:
            if created:
                page.close()                  # only a tab this run opened; never the founder's tab
            # Do not call browser.close(): on a CDP attach that can shut the signed-in Chrome.
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch Gemini scheduled actions into inbox/gemini")
    ap.add_argument("--dry-run", action="store_true", help="print row counts only, write nothing")
    ap.add_argument("--config", default=str(ROOT / "config" / "gemini_actions.yaml"))
    ap.add_argument("--inbox", default=str(ROOT / "inbox" / "gemini"))
    args = ap.parse_args(argv)
    try:
        titles = load_actions(Path(args.config))
        fetch_all(os.getenv("GEMINI_CDP_URL", "").strip() or DEFAULT_CDP, titles, Path(args.inbox),
                  dry_run=args.dry_run)
    except NeedsLogin:
        print("needs-login", file=sys.stderr)
        return 3
    except FetchError as exc:
        print(f"gemini fetch failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("gemini fetch failed: error", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
