#!/usr/bin/env python3
"""Fetch a Gemini chat (default) or scheduled actions into inbox/gemini/.

Attaches over CDP to an already signed-in Chrome (GEMINI_CDP_URL, default
http://127.0.0.1:9223). Reuses the open Gemini tab. While that tab is on
gemini.google.com this script does not call goto, reload, or new_page: a fresh
navigation from the box gets Google's unusual-traffic page. It moves by clicking
sidebar links.

Named-chat mode is the default (`source: chat` in config/gemini_actions.yaml).
GEMINI_SOURCE=chat|scheduled|both overrides the file. Scheduled mode is optional.

This script never types credentials, never types into the chat composer, never
clicks send, and never edits a schedule. The only characters it types are a
chat title from config, and only into the Search chats field, and only when
that title is not already a sidebar link.

Conversation DOM selectors, the Search chats control, and the scheduled-run
result page are NOT verified against the live Gemini page. The markdown parser
is what the unit tests run.

Exit codes:
    0  ok
    1  other failure
    2  bad config
    3  needs-login. Prints `needs-login` plus `signin` or `interstitial`
       (accounts.google.com, consent.google.com, www.google.com/sorry, or no
       "Google Account" link). A caller that raises NeedsLogin with no reason
       still prints exactly `needs-login`.
    4  none-found. Chat title not in the sidebar, no usable model response,
       or scheduled mode with no tasks. The line says which.
    5  unparsed. Model responses exist, but none has an http(s) table row or a
       "Sources checked" line. No row is invented.

`--probe` prints only structure (url path, selector, response count, table-row
count, sidebar titles) and writes nothing. It exits 0 when that page could be
read, 3 on needs-login, and 4 when the chat title is not in the sidebar.
`--dry-run` prints row counts only and writes nothing. Both flags default off.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.briefing.gemini_inbox import SG, parse_markdown_response  # noqa: E402

APP_URL = "https://gemini.google.com/app"
DEFAULT_CDP = "http://127.0.0.1:9223"
_ROW_KEYS = ("topic", "headline", "publisher", "published", "link", "sentence")
_SCHEDULED = (re.compile(r"scheduled actions", re.I), re.compile(r"^scheduled$", re.I))
_MODES = ("chat", "scheduled", "both")
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_DATE_DMY = re.compile(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b")
_DATE_MDY = re.compile(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
POLL_MS = 500
RESPONSE_WAIT_S = 30
MAX_RESPONSES = 8

# All selectors live here. `response` is tried in order. The name we log is the
# first candidate that supplies model text. user-query never counts as a model
# response. These conversation selectors are NOT verified live.
SELECTORS = {
    "response": (
        ("model-response", "css", "model-response"),
        ("user-query", "css", "user-query"),
        ("data-message-id", "css", "[data-message-id]"),
        ("article", "role", "article"),
        ("aria-live", "css", "[aria-live]"),
    ),
    "sidebar": ("nav", '[role="navigation"]', "aside"),
    "conversation": ("main", '[role="main"]'),
    "chat_href": 'a[href*="/app/"]',
    "search_button": "Search chats",
}


class NeedsLogin(Exception):
    def __init__(self, reason: str = ""):
        self.reason = reason
        super().__init__(reason)


class FetchError(Exception):
    """A failure whose message is safe to print (no page body, no key)."""


class ConfigError(Exception):
    pass


class NoneFound(Exception):
    pass


class Unparsed(Exception):
    pass


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


def login_reason(url: str) -> str:
    """`signin`, `interstitial`, or empty when the URL itself is not a wall."""
    if not login_wall(url):
        return ""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.endswith("google.com") and parts.path.startswith("/sorry"):
        return "interstitial"
    return "signin"


def is_gemini_host(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == "gemini.google.com"


def slugify(title: str) -> str:
    text = title.lower().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "action"


def load_config(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        raise ConfigError("unreadable config") from None
    except yaml.YAMLError:
        raise ConfigError("invalid yaml") from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("config is not a mapping")
    return data


def source_mode(data: dict) -> str:
    """File `source:` (default chat). GEMINI_SOURCE overrides when set."""
    env = os.getenv("GEMINI_SOURCE", "").strip().lower()
    if env:
        if env not in _MODES:
            raise ConfigError("GEMINI_SOURCE must be chat, scheduled, or both")
        return env
    raw = str((data or {}).get("source") or "chat").strip().lower()
    if raw not in _MODES:
        raise ConfigError("source must be chat, scheduled, or both")
    return raw


def chats_from(data: dict) -> list[dict]:
    raw = (data or {}).get("chats")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError("chats must be a list")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigError("chat entry must be a mapping")
        title = str(item.get("title") or "").strip()
        label = str(item.get("label") or "").strip()
        if not title or not label:
            raise ConfigError("chat needs title and label")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", label):
            raise ConfigError("chat label must be a slug")
        out.append({"title": title, "label": label})
    return out


def actions_from(data: dict, *, required: bool = True) -> list[str]:
    titles = []
    for item in (data or {}).get("actions") or []:
        if isinstance(item, str) and item.strip():
            titles.append(item.strip())
        elif isinstance(item, dict) and str(item.get("title") or "").strip():
            titles.append(str(item["title"]).strip())
    if required and not titles:
        raise ConfigError("no actions configured")
    return titles


def load_actions(path: Path) -> list[str]:
    return actions_from(load_config(path))


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def _row_out(row: dict) -> dict[str, str]:
    return {k: str(row.get(k) or "")[:500] for k in _ROW_KEYS}


def record_result(inbox: Path, title: str, text: str, *, dry_run: bool,
                  now: dt.datetime | None = None, label: str | None = None) -> int:
    """Write inbox/gemini/<date>-<label-or-action>.md and .json. Dry-run writes nothing.
    Returns the row count. Prints only the count when dry_run is set.
    `action` in the json is the title (the chat title in chat mode)."""
    parsed = parse_markdown_response(text)
    n = len(parsed["rows"])
    if dry_run:
        print(f"{title}: {n} rows")
        return n
    moment = (now or dt.datetime.now(SG)).astimezone(SG)
    inbox.mkdir(parents=True, exist_ok=True)
    stem_bit = slugify(label) if label else slugify(title)
    stem = f"{moment.date().isoformat()}-{stem_bit}"
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


def _as_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def stated_dates(text: str) -> list[dt.date]:
    """Calendar dates written in the text. Slash dates are ignored (too ambiguous)."""
    found: list[dt.date] = []
    for match in _DATE_ISO.finditer(text or ""):
        item = _as_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if item:
            found.append(item)
    for match in _DATE_DMY.finditer(text or ""):
        month = _MONTHS.get(match.group(2).lower())
        if month:
            item = _as_date(int(match.group(3)), month, int(match.group(1)))
            if item:
                found.append(item)
    for match in _DATE_MDY.finditer(text or ""):
        month = _MONTHS.get(match.group(1).lower())
        if month:
            item = _as_date(int(match.group(3)), month, int(match.group(2)))
            if item:
                found.append(item)
    return found


def response_date_ok(text: str, today: dt.date) -> bool:
    """A response that states a date must state today in Asia/Singapore.

    A date outside the markdown table is the response's own date. Article dates
    inside the table count only when the response states no date outside it.
    A response that states no date is not rejected.
    """
    outside = "\n".join(ln for ln in (text or "").splitlines() if not ln.strip().startswith("|"))
    outside_dates = stated_dates(outside)
    if outside_dates:
        return today in outside_dates
    dates = stated_dates(text)
    if not dates:
        return True
    return today in dates


def _sources_checked(text: str) -> bool:
    for line in (text or "").splitlines():
        if re.search(r"\bSources checked\b", line.strip()):
            return True
    return False


def _has_http_row(text: str) -> bool:
    parsed = parse_markdown_response(text)
    for row in parsed["rows"]:
        link = str(row.get("link") or "").strip()
        if link.startswith("https://") or link.startswith("http://"):
            return True
    return False


def pick_response(texts: list[str], today: dt.date) -> tuple[str, str]:
    """Newest first, at most 8 non-empty model responses.

    Returns (status, text). status is ok, unparsed, stale, or none.
    ok means the first response that has an http(s) table row or a
    "Sources checked" line, and is not dated on another day.
    """
    window = [t.strip() for t in texts if t and t.strip()][-MAX_RESPONSES:]
    if not window:
        return "none", ""
    stale = False
    for text in reversed(window):
        if not (_has_http_row(text) or _sources_checked(text)):
            continue
        if not response_date_ok(text, today):
            stale = True
            continue
        return "ok", text
    if stale:
        return "stale", ""
    return "unparsed", ""


class _Fragment(HTMLParser):
    """Turn a model-response fragment into text plus markdown tables. No invented rows."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._href: str | None = None

    def _push(self, text: str) -> None:
        if self._skip or self._tables:
            return
        self.parts.append(text)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr = {k.lower(): v for k, v in attrs}
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "table":
            self._tables.append([])
            return
        if self._tables and tag == "tr":
            self._row = []
            return
        if self._tables and tag in ("td", "th"):
            self._cell = []
            self._href = None
            return
        if tag == "a" and self._cell is not None and self._href is None:
            href = attr.get("href") or ""
            if href.startswith("http://") or href.startswith("https://"):
                self._href = href
            return
        if tag == "br":
            self._push("\n")
        elif tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self._push("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("td", "th") and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            if self._href and "http" not in text:
                value = self._href
            else:
                value = text or (self._href or "")
            if self._row is not None:
                self._row.append(value.replace("|", "/"))
            self._cell = None
            self._href = None
            return
        if tag == "tr" and self._row is not None and self._tables:
            self._tables[-1].append(self._row)
            self._row = None
            return
        if tag == "table" and self._tables:
            rows = self._tables.pop()
            self.parts.append("\n" + _rows_to_markdown(rows) + "\n")
            return
        if tag in ("p", "div", "li"):
            self._push("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
            return
        if self._tables:
            return
        self.parts.append(data)


def _rows_to_markdown(rows: list[list[str]]) -> str:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = []
    for i, row in enumerate(rows):
        cells = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
    return "\n".join(lines)


def html_to_response(fragment: str) -> str:
    parser = _Fragment()
    parser.feed(fragment or "")
    parser.close()
    text = re.sub(r"\n{3,}", "\n\n", "".join(parser.parts))
    return text.strip()


def _signed_in(page) -> bool:
    """The signed-in Gemini shell has a "Google Account: <name>" link in the sidebar. A signed-out
    visit shows a "Sign in" link instead."""
    if page.get_by_role("link", name=re.compile(r"^Google Account", re.I)).count():
        return True
    return False


def _guard(page, *, need_account: bool = False) -> None:
    reason = login_reason(page.url)
    if reason:
        raise NeedsLogin(reason)
    if need_account and not _signed_in(page):
        raise NeedsLogin("signin")


def _enter(page) -> None:
    """Stand on the founder's tab. Never goto when that tab is already on Gemini."""
    _guard(page)
    if not is_gemini_host(page.url):
        page.goto(APP_URL, wait_until="domcontentloaded")
    _guard(page)
    page.wait_for_timeout(1500)
    _guard(page, need_account=True)


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


def _query(page, kind: str, spec: str):
    if kind == "role":
        return page.get_by_role(spec)
    return page.locator(spec)


def _user_authored(el) -> bool:
    author = (el.get_attribute("data-author") or el.get_attribute("data-message-author") or "")
    return author.strip().lower() in ("user", "human")


def _safe_eval(loc, script: str) -> None:
    try:
        loc.evaluate(script)
    except Exception:
        return


def _scroll_sidebar(page) -> None:
    for css in SELECTORS["sidebar"]:
        loc = page.locator(css)
        if loc.count():
            _safe_eval(loc.first, "node => { node.scrollTop = node.scrollHeight; }")
            return


def _scroll_conversation(page) -> None:
    """Scroll the conversation to the bottom so a virtualised list paints the newest turns."""
    for css in SELECTORS["conversation"]:
        loc = page.locator(css)
        if loc.count():
            _safe_eval(loc.first, "node => { node.scrollTop = node.scrollHeight; }")
    for name, kind, spec in SELECTORS["response"]:
        if name == "user-query":
            continue
        loc = _query(page, kind, spec)
        count = loc.count()
        if count:
            _safe_eval(loc.nth(count - 1), "node => node.scrollIntoView()")
            return


def _search_box(page):
    """The Search chats field only. Never the chat composer."""
    candidates = (
        page.get_by_role("searchbox"),
        page.get_by_role("textbox", name=re.compile(r"^Search chats$", re.I)),
        page.locator('input[aria-label="Search chats"]'),
        page.locator('input[placeholder="Search chats"]'),
    )
    for loc in candidates:
        if loc.count():
            return loc
    return None


def _focus_search(page, title: str) -> bool:
    button = page.get_by_role("button", name=SELECTORS["search_button"], exact=True)
    if not button.count():
        return False
    button.first.click()
    box = _search_box(page)
    if box is None:
        return False
    # `title` is the configured chat title. Nothing else is typed.
    box.first.press_sequentially(title)
    page.wait_for_timeout(300)
    return True


def _click_chat_link(page, title: str) -> bool:
    """Exact accessible text, first sidebar chat link whose href contains /app/."""
    links = page.locator(SELECTORS["chat_href"])
    want = _norm(title)
    for i in range(links.count()):
        el = links.nth(i)
        if _norm(el.inner_text()) == want:
            el.click()
            return True
    return False


def _open_chat(page, title: str) -> None:
    if _click_chat_link(page, title):
        _guard(page, need_account=True)
        return
    _scroll_sidebar(page)
    if _click_chat_link(page, title):
        _guard(page, need_account=True)
        return
    if _focus_search(page, title) and _click_chat_link(page, title):
        _guard(page, need_account=True)
        return
    raise NoneFound(f"chat title not in sidebar: {title}")


def collect_model_responses(page) -> tuple[str, list[str]]:
    """Try SELECTORS['response'] in order. Log name is the one that supplied model text."""
    first_hit = ""
    for name, kind, spec in SELECTORS["response"]:
        loc = _query(page, kind, spec)
        count = loc.count()
        if not count:
            continue
        if not first_hit:
            first_hit = name
        if name == "user-query":
            continue
        texts = []
        for i in range(count):
            el = loc.nth(i)
            if name == "data-message-id" and _user_authored(el):
                continue
            try:
                raw = el.inner_html()
            except Exception:
                raise FetchError("response read failed") from None
            text = html_to_response(raw or "")
            if text.strip():
                texts.append(text)
        if texts:
            return name, texts
    return first_hit, []


def _wait_responses(page) -> tuple[str, list[str]]:
    ticks = int(RESPONSE_WAIT_S * 1000 / POLL_MS)
    selector, texts = "", []
    for _ in range(ticks):
        _scroll_conversation(page)
        selector, texts = collect_model_responses(page)
        if texts:
            _scroll_conversation(page)
            return collect_model_responses(page)
        page.wait_for_timeout(POLL_MS)
    return selector, texts


def _title_visible(page, title: str) -> bool:
    pat = re.compile(re.escape(title), re.I)
    for role in ("link", "button", "tab"):
        if page.get_by_role(role, name=pat).count():
            return True
    return bool(page.get_by_text(pat).count())


def sidebar_titles(page) -> list[str]:
    """Sidebar link names only. No href, no query string, no message text."""
    links = page.locator("a")
    out = []
    for i in range(links.count()):
        el = links.nth(i)
        href = (el.get_attribute("href") or "").split("?", 1)[0]
        name = _norm(el.inner_text())
        if not name:
            continue
        if (
            "/app/" in href
            or href.rstrip("/").endswith("/scheduled")
            or href == "scheduled"
            or name.lower().startswith("google account")
            or name.lower() == "scheduled"
        ):
            out.append(name)
    return out


def format_probe(path: str, selector: str, responses: int, table_rows: int, sidebar: list[str]) -> str:
    shown = list(sidebar[:40])
    extra = len(sidebar) - len(shown)
    side = " | ".join(shown)
    if extra > 0:
        side = f"{side} | (+{extra} more)"
    return "\n".join([
        f"path: {path or '/'}",
        f"selector: {selector or 'none'}",
        f"responses: {responses}",
        f"table_rows: {table_rows}",
        f"sidebar: {side}",
    ])


def _emit_probe(page, selector: str, texts: list[str]) -> None:
    rows = 0
    for text in texts:
        rows += len(parse_markdown_response(text)["rows"])
    path = urlsplit(page.url).path or "/"
    print(format_probe(path, selector, len(texts), rows, sidebar_titles(page)))


def _finish_text(selector: str, texts: list[str], title: str, label: str | None, *,
                 inbox: Path, dry_run: bool, now, today: dt.date) -> None:
    if selector:
        print(f"selector: {selector}", file=sys.stderr)
    status, text = pick_response(texts, today)
    if status == "ok":
        record_result(inbox, title, text, dry_run=dry_run, now=now, label=label)
        return
    if status == "unparsed":
        raise Unparsed(title)
    if status == "stale":
        raise NoneFound(f"no response from today: {title}")
    raise NoneFound(f"no model response: {title}")


def _run_chat(page, chat: dict, *, inbox, dry_run, probe, now, today) -> None:
    title = chat["title"]
    try:
        _open_chat(page, title)
    except NoneFound:
        if probe:
            _emit_probe(page, "", [])
        raise
    if probe:
        selector, texts = _wait_responses(page)
        _emit_probe(page, selector, texts)
        return
    selector, texts = _wait_responses(page)
    _finish_text(selector, texts, title, chat["label"], inbox=inbox, dry_run=dry_run, now=now, today=today)


def _run_scheduled(page, titles: list[str], *, inbox, dry_run, probe, now, today, mode: str) -> None:
    _open_scheduled(page)
    _guard(page, need_account=True)
    if probe:
        _scroll_conversation(page)
        selector, texts = collect_model_responses(page)
        _emit_probe(page, selector, texts)
        return
    skipped = 0
    opened = 0
    for title in titles:
        if not _title_visible(page, title):
            skipped += 1
            continue
        if opened:
            _back_to_list(page)
        _open_action(page, title)
        _guard(page, need_account=True)
        selector, texts = _wait_responses(page)
        _finish_text(selector, texts, title, None, inbox=inbox, dry_run=dry_run, now=now, today=today)
        opened += 1
    if skipped:
        print(f"scheduled skipped: {skipped}")
    if opened == 0 and mode == "scheduled":
        raise NoneFound("no scheduled tasks")


def run_page(page, *, mode: str, chats: list[dict], titles: list[str], inbox: Path,
             dry_run: bool, probe: bool, now: dt.datetime | None = None) -> None:
    """Read the open page. Raises NeedsLogin, NoneFound, Unparsed, or FetchError."""
    _enter(page)
    today = (now or dt.datetime.now(SG)).astimezone(SG).date()
    if mode in ("chat", "both"):
        for chat in chats:
            _run_chat(page, chat, inbox=inbox, dry_run=dry_run, probe=probe, now=now, today=today)
            if probe:
                return
    if mode in ("scheduled", "both"):
        _run_scheduled(page, titles, inbox=inbox, dry_run=dry_run, probe=probe, now=now, today=today, mode=mode)


def fetch_all(cdp_url: str, inbox: Path, *, dry_run: bool, probe: bool = False,
               mode: str = "chat", chats: list[dict] | None = None,
               titles: list[str] | None = None, now: dt.datetime | None = None) -> None:
    """Attach to Chrome and read. Leaves Chrome and its tab open."""
    from playwright.sync_api import sync_playwright

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
            run_page(page, mode=mode, chats=list(chats or []), titles=list(titles or []),
                     inbox=inbox, dry_run=dry_run, probe=probe, now=now)
        finally:
            if created:
                page.close()                  # only a tab this run opened; never the founder's tab
            # Do not call browser.close(): on a CDP attach that can shut the signed-in Chrome.


def exit_for(exc: BaseException) -> int | None:
    """Map a known failure to an exit code. Prints one safe line. None if unknown."""
    if isinstance(exc, NeedsLogin):
        reason = getattr(exc, "reason", "") or ""
        if reason:
            print(f"needs-login {reason}", file=sys.stderr)
        else:
            print("needs-login", file=sys.stderr)
        return 3
    if isinstance(exc, NoneFound):
        print(f"none-found: {exc}", file=sys.stderr)
        return 4
    if isinstance(exc, Unparsed):
        print(f"unparsed: {exc}", file=sys.stderr)
        return 5
    if isinstance(exc, ConfigError):
        print(f"bad config: {exc}", file=sys.stderr)
        return 2
    if isinstance(exc, FetchError):
        print(f"gemini fetch failed: {exc}", file=sys.stderr)
        return 1
    return None


def drive(page, **kwargs) -> int:
    """Same exit mapping as main(), for a page that is already open. No network."""
    try:
        run_page(page, **kwargs)
    except Exception as exc:
        code = exit_for(exc)
        if code is None:
            print("gemini fetch failed: error", file=sys.stderr)
            return 1
        return code
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch a Gemini chat or scheduled actions into inbox/gemini")
    ap.add_argument("--dry-run", action="store_true", help="print row counts only, write nothing")
    ap.add_argument("--probe", action="store_true", help="print page structure only, write nothing")
    ap.add_argument("--config", default=str(ROOT / "config" / "gemini_actions.yaml"))
    ap.add_argument("--inbox", default=str(ROOT / "inbox" / "gemini"))
    args = ap.parse_args(argv)
    try:
        data = load_config(Path(args.config))
        mode = source_mode(data)
        chats = chats_from(data) if mode in ("chat", "both") else []
        if mode in ("chat", "both") and not chats:
            raise ConfigError("no chats configured")
        if mode == "scheduled":
            titles = actions_from(data, required=True)
        elif mode == "both":
            titles = actions_from(data, required=False)
        else:
            titles = []
        fetch_all(
            os.getenv("GEMINI_CDP_URL", "").strip() or DEFAULT_CDP,
            Path(args.inbox),
            dry_run=args.dry_run,
            probe=args.probe,
            mode=mode,
            chats=chats,
            titles=titles,
        )
    except Exception as exc:
        code = exit_for(exc)
        if code is None:
            print("gemini fetch failed: error", file=sys.stderr)
            return 1
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
