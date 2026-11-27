"""Gemini chat fetch. Synthetic HTML fixtures, no network, no browser.

Every shipped HTML file under tests/fixtures/gemini/synthetic_*.html is labelled
synthetic. Markers below are test sentinels, not live page text.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "gemini"
SG = ZoneInfo("Asia/Singapore")
NOW = dt.datetime(2026, 11, 27, 9, 0, tzinfo=SG)
TODAY = NOW.date()
CHAT = "AI Briefing Automation Setup"
ACTIONS = ["Morning scout", "Market check", "Editor's check before posting", "Evening scout"]
APP = "https://gemini.google.com/app"


def _load():
    spec = importlib.util.spec_from_file_location("gemini_fetch_chat", ROOT / "scripts" / "gemini_fetch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gf = _load()


def _html(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _norm(text: str) -> str:
    return " ".join((text or "").split())


_ATTR = re.compile(
    r"^(?P<tag>[a-zA-Z0-9-]*)\[(?P<attr>[A-Za-z_:][-A-Za-z0-9_:]*)(?P<op>[*$])?=(?P<q>[\"'])(?P<val>.*?)(?P=q)\]$"
)
_BARE = re.compile(r"^\[(?P<attr>[A-Za-z_:][-A-Za-z0-9_:]*)\]$")
_TAG = re.compile(r"^[A-Za-z0-9-]+$")
_VOID = {"input", "br", "img", "meta", "link", "hr"}
_BLOCK = {"p", "div", "li", "h1", "h2", "h3", "tr", "table", "main", "nav", "section"}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []

    def inner_text(self) -> str:
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                if child.tag in _BLOCK:
                    parts.append("\n")
                parts.append(child.inner_text())
                if child.tag in _BLOCK:
                    parts.append("\n")
        return "".join(parts)

    def inner_html(self) -> str:
        chunks = []
        for child in self.children:
            if isinstance(child, str):
                chunks.append(child)
            else:
                attrs = "".join(f' {k}="{v}"' for k, v in child.attrs.items())
                chunks.append(f"<{child.tag}{attrs}>{child.inner_html()}</{child.tag}>")
        return "".join(chunks)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def _css_one(node: Node, selector: str) -> bool:
    selector = selector.strip()
    matched = _ATTR.match(selector)
    if matched:
        if matched.group("tag") and node.tag != matched.group("tag").lower():
            return False
        val = node.attrs.get(matched.group("attr").lower())
        if val is None:
            return False
        op = matched.group("op")
        want = matched.group("val")
        if op == "*":
            return want in val
        if op == "$":
            return val.endswith(want)
        return val == want
    bare = _BARE.match(selector)
    if bare:
        return bare.group("attr").lower() in node.attrs
    if _TAG.match(selector):
        return node.tag == selector.lower()
    return False


def _role_is(node: Node, role: str) -> bool:
    if (node.attrs.get("role") or "").lower() == role:
        return True
    if role == "link":
        return node.tag == "a"
    if role == "button":
        return node.tag == "button"
    if role == "article":
        return node.tag == "article"
    if role == "main":
        return node.tag == "main"
    if role == "searchbox":
        return node.tag == "input" and node.attrs.get("type") == "search"
    if role == "textbox":
        if node.tag == "textarea":
            return True
        return node.tag == "input" and node.attrs.get("type", "text") in ("text", "")
    return False


class Locator:
    def __init__(self, page, nodes):
        self.page = page
        self.nodes = list(nodes)

    def count(self):
        return len(self.nodes)

    @property
    def first(self):
        return Locator(self.page, self.nodes[:1])

    def nth(self, i):
        if i < 0 or i >= len(self.nodes):
            return Locator(self.page, [])
        return Locator(self.page, [self.nodes[i]])

    def _only(self):
        if len(self.nodes) != 1:
            raise AssertionError(f"expected one node, got {len(self.nodes)}")
        return self.nodes[0]

    def click(self):
        node = self._only()
        self.page.clicks.append((node.tag, _norm(node.inner_text())[:120]))
        href = node.attrs.get("href")
        if node.tag == "a" and href:
            self.page.url = urljoin(self.page.url, href)
            self.page.history.append(self.page.url)

    def inner_text(self):
        return self._only().inner_text()

    def inner_html(self):
        return self._only().inner_html()

    def get_attribute(self, name):
        return self._only().attrs.get(name.lower())

    def press_sequentially(self, text):
        node = self._only()
        self.page.typed.append(text)
        self.page.typed_on.append(f"{node.tag}:{node.attrs.get('aria-label', '')}:{node.attrs.get('type', '')}")
        if node.attrs.get("type") == "search" or node.attrs.get("aria-label") == "Search chats":
            self.page.search_query = text

    def evaluate(self, script):
        node = self._only()
        self.page.evals.append(script)
        if node.tag in ("nav", "aside") or node.attrs.get("role") == "navigation":
            self.page.sidebar_scrolled = True
        else:
            self.page.conversation_scrolled = True


class FixturePage:
    """Enough of a page to run gemini_fetch against a synthetic HTML snapshot."""

    def __init__(self, html: str, url: str):
        self.root = _Tree()
        self.root.feed(html)
        self.root.close()
        self.root = self.root.root
        self.url = url
        self.history = [url]
        self.typed = []
        self.typed_on = []
        self.clicks = []
        self.gotos = []
        self.waits = []
        self.evals = []
        self.sidebar_scrolled = False
        self.conversation_scrolled = False
        self.search_query = ""

    def _walk(self, node=None):
        node = self.root if node is None else node
        for child in node.children:
            if isinstance(child, str):
                continue
            yield child
            yield from self._walk(child)

    def _visible(self, node: Node) -> bool:
        cur = node
        while cur is not None and cur.tag != "document":
            if cur.attrs.get("data-offscreen") == "1" and not self.sidebar_scrolled:
                return False
            if cur.attrs.get("data-search") == "1" and self.search_query != _norm(cur.inner_text()):
                return False
            cur = cur.parent
        return True

    def _name_ok(self, node: Node, name, exact) -> bool:
        accessible = _norm(node.inner_text())
        if hasattr(name, "search"):
            return bool(name.search(accessible))
        if exact:
            return accessible == name
        return str(name).lower() in accessible.lower()

    def get_by_role(self, role, name=None, exact=None):
        found = []
        for node in self._walk():
            if not self._visible(node) or not _role_is(node, role.lower()):
                continue
            if name is not None and not self._name_ok(node, name, exact):
                continue
            found.append(node)
        return Locator(self, found)

    def get_by_text(self, pat):
        found = []
        for node in self._walk():
            if self._visible(node) and pat.search(node.inner_text() or ""):
                found.append(node)
        return Locator(self, found)

    def locator(self, selector):
        parts = [p.strip() for p in selector.split(",")]
        found = []
        for node in self._walk():
            if self._visible(node) and any(_css_one(node, part) for part in parts):
                found.append(node)
        return Locator(self, found)

    def goto(self, url, wait_until=None):
        self.gotos.append(url)
        self.url = url
        self.history.append(url)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            self.url = self.history[-1]

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def wait_for_url(self, pat, timeout=None):
        if not pat.search(self.url):
            raise TimeoutError(urlsplit_path(self.url))

    def set_default_timeout(self, ms):
        return None


def urlsplit_path(url: str) -> str:
    from urllib.parse import urlsplit
    return urlsplit(url).path or "/"


def run(html: str, url: str, inbox: Path, **over):
    page = FixturePage(html, url)
    kw = dict(mode="chat", chats=[{"title": CHAT, "label": "briefing"}], titles=[],
              inbox=inbox, dry_run=False, probe=False, now=NOW)
    kw.update(over)
    code = gf.drive(page, **kw)
    return code, page


def _saved(inbox: Path, stem: str) -> dict:
    return json.loads((inbox / f"{stem}.json").read_text(encoding="utf-8"))


# ── pure decisions ───────────────────────────────────────────────────────────
def test_login_reason_and_patch_navigation_rules():
    assert gf.login_reason("https://accounts.google.com/ServiceLogin") == "signin"
    assert gf.login_reason("https://consent.google.com/m?continue=x") == "signin"
    assert gf.login_reason("https://www.google.com/sorry/index?continue=https://gemini.google.com/app") == "interstitial"
    assert gf.login_reason("https://gemini.google.com/app") == ""
    text = (ROOT / "scripts" / "gemini_fetch.py").read_text(encoding="utf-8")
    assert text.count("page.goto(") == 1
    assert "page.reload" not in text
    assert 'a[href$="/scheduled"], a[href="scheduled"]' in text
    for banned in (".fill(", ".type(", "keyboard", "insert_text"):
        assert banned not in text

    class P:
        def __init__(self, url):
            self.url = url

    class Ctx:
        def __init__(self, pages):
            self.pages = pages
            self.made = 0

        def new_page(self):
            self.made += 1
            return P("about:blank")

    ctx = Ctx([P("https://gemini.google.com/scheduled")])
    page, created = gf._pick_page(ctx)
    assert created is False and ctx.made == 0 and page.url.endswith("/scheduled")
    ctx = Ctx([P("https://www.google.com/sorry/index")])
    _, created = gf._pick_page(ctx)
    assert created is False and ctx.made == 0
    ctx = Ctx([P("https://example.com/")])
    _, created = gf._pick_page(ctx)
    assert created is True and ctx.made == 1


def test_source_defaults_to_chat_and_env_overrides(monkeypatch):
    monkeypatch.delenv("GEMINI_SOURCE", raising=False)
    assert gf.source_mode({}) == "chat"
    assert gf.source_mode({"source": "scheduled"}) == "scheduled"
    monkeypatch.setenv("GEMINI_SOURCE", "both")
    assert gf.source_mode({"source": "chat"}) == "both"
    titles = gf.load_actions(ROOT / "config" / "gemini_actions.yaml")
    assert titles == ACTIONS
    chats = gf.chats_from(gf.load_config(ROOT / "config" / "gemini_actions.yaml"))
    assert chats == [{"title": CHAT, "label": "briefing"}]


def test_pick_response_rules():
    row = (
        "| Topic | Headline | Publisher | Published | Link | Sentence |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| T | H | Reuters | 27 Nov 2026 06:00 SGT | https://example.com/a | one |\n"
    )
    assert gf.pick_response([""], TODAY)[0] == "none"
    assert gf.pick_response(["a paragraph with no table"], TODAY)[0] == "unparsed"
    assert gf.pick_response(["Sources checked: 1"], TODAY)[0] == "ok"
    assert gf.pick_response([row + "\nSources checked: 1\n"], TODAY)[0] == "ok"
    stale = "26 Nov 2026\n" + row + "\nSources checked: 1\n"
    fresh = "27 Nov 2026\n" + row.replace("example.com/a", "example.com/fresh") + "\nSources checked: 1\n"
    status, text = gf.pick_response([fresh, stale], TODAY)
    assert status == "ok" and "example.com/fresh" in text
    assert gf.pick_response([stale], TODAY)[0] == "stale"
    ancient = row.replace("example.com/a", "example.com/ancient")
    noise = ["no table here"] * 8
    assert gf.pick_response([ancient, *noise], TODAY)[0] == "unparsed"
    html = (
        "<p>27 Nov 2026</p><table><tr><th>Link</th></tr>"
        '<tr><td><a href="https://example.com/html">story</a></td></tr></table>'
        "<p>Sources checked: 1</p>"
    )
    converted = gf.html_to_response(html)
    assert gf.pick_response([converted], TODAY)[0] == "ok"
    assert "https://example.com/html" in converted
    assert gf.pick_response([gf.html_to_response("<p>synthetic fixture, no table</p>")], TODAY)[0] == "unparsed"


def test_record_result_uses_the_label_and_keeps_the_schema(tmp_path):
    body = (FIX / "morning_scout.md").read_text(encoding="utf-8")
    n = gf.record_result(tmp_path, CHAT, body, dry_run=False, now=NOW, label="briefing")
    assert n == 2
    saved = _saved(tmp_path, "2026-11-27-briefing")
    raw = (tmp_path / "2026-11-27-briefing.md").read_text(encoding="utf-8")
    assert saved["action"] == CHAT
    assert saved["source_url"] == gf.APP_URL
    assert saved["sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert "Sources checked" in saved["closing"]
    assert saved["rows"][0]["link"].startswith("https://")


# ── exit codes on synthetic pages ────────────────────────────────────────────
def test_signed_out_landing_exits_3_signin(tmp_path, capsys):
    code, page = run(_html("synthetic_signed_out.html"), APP, tmp_path)
    err = capsys.readouterr().err
    assert code == 3
    assert err.strip() == "needs-login signin"
    assert page.clicks == [] and page.gotos == []


def test_sorry_page_exits_3_interstitial(tmp_path, capsys):
    code, page = run(_html("synthetic_sorry.html"), "https://www.google.com/sorry/index?continue=secret", tmp_path)
    captured = capsys.readouterr()
    assert code == 3
    assert captured.err.strip() == "needs-login interstitial"
    assert "secret" not in captured.err and "secret" not in captured.out
    assert page.waits == [] and page.gotos == []


def test_consent_host_exits_3_signin(tmp_path, capsys):
    html = "<!-- synthetic fixture --><a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
    code, page = run(html, "https://consent.google.com/m", tmp_path)
    assert code == 3
    assert capsys.readouterr().err.strip() == "needs-login signin"
    assert page.gotos == []


def test_conversation_with_table_exits_0(tmp_path, capsys):
    code, page = run(_html("synthetic_sidebar_with_chat.html"), APP, tmp_path)
    captured = capsys.readouterr()
    assert code == 0
    assert page.gotos == []
    assert ("a", CHAT) in page.clicks
    assert ("button", "More options for AI Briefing Automation Setup") not in page.clicks
    assert ("a", "Scheduled") not in page.clicks
    assert page.typed == []
    assert "selector: model-response" in captured.err
    assert "BODYMARKER" not in captured.out and "BODYMARKER" not in captured.err
    assert "ARTICLEMARKER" not in captured.out and "USERMARKER" not in captured.err
    saved = _saved(tmp_path, "2026-11-27-briefing")
    raw = (tmp_path / "2026-11-27-briefing.md").read_text(encoding="utf-8")
    assert saved["action"] == CHAT
    assert saved["sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert saved["rows"][0]["link"] == "https://www.reuters.com/world/example"
    assert "ARTICLEMARKER" not in raw and "USERMARKER" not in raw
    assert {p.name for p in tmp_path.iterdir()} == {"2026-11-27-briefing.md", "2026-11-27-briefing.json"}


def test_sidebar_without_the_chat_exits_4(tmp_path, capsys):
    code, page = run(_html("synthetic_sidebar_without_chat.html"), APP, tmp_path)
    captured = capsys.readouterr()
    assert code == 4
    assert captured.err.strip() == f"none-found: chat title not in sidebar: {CHAT}"
    assert page.typed == [CHAT]
    assert page.typed_on == ["input:Search chats:search"]
    assert page.gotos == []
    assert list(tmp_path.iterdir()) == []
    assert "Some Other Chat" not in captured.err


def test_conversation_without_a_table_exits_5(tmp_path, capsys):
    code, _page = run(_html("synthetic_conversation_notable.html"), APP, tmp_path)
    captured = capsys.readouterr()
    assert code == 5
    assert "unparsed: AI Briefing Automation Setup" in captured.err
    assert "notable-paragraph-marker" not in captured.err and "notable-paragraph-marker" not in captured.out
    assert list(tmp_path.iterdir()) == []


def test_empty_conversation_exits_4_after_the_full_wait(tmp_path, capsys):
    code, page = run(_html("synthetic_conversation_empty.html"), APP, tmp_path)
    captured = capsys.readouterr()
    assert code == 4
    assert captured.err.strip() == f"none-found: no model response: {CHAT}"
    assert "Where should we start?" not in captured.out and "Where should we start?" not in captured.err
    assert page.waits.count(500) == int(gf.RESPONSE_WAIT_S * 1000 / gf.POLL_MS)
    assert page.gotos == []
    assert list(tmp_path.iterdir()) == []


def test_stale_response_exits_4_and_an_older_today_response_is_kept(tmp_path, capsys):
    stale = _html("synthetic_sidebar_with_chat.html").replace("27 Nov 2026", "26 Nov 2026")
    code, _page = run(stale, APP, tmp_path)
    assert code == 4
    assert "no response from today" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
    older = (
        "<!-- synthetic fixture --><nav>"
        "<a href='/scheduled'>Scheduled</a>"
        f"<a href='/app/a1'> {CHAT} </a>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a></nav><main>"
        "<model-response>27 Nov 2026\n"
        "| Link |\n| --- |\n| https://example.com/older |\n\nSources checked: 1</model-response>"
        "<model-response>26 Nov 2026\n"
        "| Link |\n| --- |\n| https://example.com/newer |\n\nSources checked: 1</model-response>"
        "</main>"
    )
    code, _page = run(older, APP, tmp_path)
    assert code == 0
    raw = (tmp_path / "2026-11-27-briefing.md").read_text(encoding="utf-8")
    assert "https://example.com/older" in raw and "https://example.com/newer" not in raw


def test_sources_checked_without_a_table_is_kept_and_rows_stay_empty(tmp_path, capsys):
    html = (
        "<!-- synthetic fixture --><nav>"
        "<a href='/scheduled'>Scheduled</a>"
        f"<a href='/app/a1'>{CHAT}</a>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a></nav>"
        "<main><model-response>Sources checked: 1</model-response></main>"
    )
    code, _page = run(html, APP, tmp_path)
    assert code == 0
    saved = _saved(tmp_path, "2026-11-27-briefing")
    assert saved["rows"] == []
    assert "Sources checked" in saved["closing"]
    assert "BODYMARKER" not in capsys.readouterr().out


def test_probe_prints_structure_only(tmp_path, capsys):
    code, page = run(_html("synthetic_sidebar_with_chat.html"), APP, tmp_path, probe=True)
    captured = capsys.readouterr()
    assert code == 0 and page.gotos == [] and list(tmp_path.iterdir()) == []
    lines = captured.out.strip().splitlines()
    assert lines[0] == "path: /app/a1b2c3d4"
    assert lines[1] == "selector: model-response"
    assert lines[2] == "responses: 1"
    assert lines[3] == "table_rows: 1"
    assert "AI Briefing Automation Setup" in lines[4]
    assert "BODYMARKER" not in captured.out and "ARTICLEMARKER" not in captured.out
    assert "USERMARKER" not in captured.out and "BODYMARKER" not in captured.err
    code, _page = run(_html("synthetic_sidebar_without_chat.html"), APP, tmp_path, probe=True)
    captured = capsys.readouterr()
    assert code == 4
    assert "sidebar:" in captured.out and "Some Other Chat" in captured.out
    assert "synthetic fixture" not in captured.out


def test_probe_empty_conversation_reports_zero_responses(tmp_path, capsys):
    code, _page = run(_html("synthetic_conversation_empty.html"), APP, tmp_path, probe=True)
    captured = capsys.readouterr()
    assert code == 0
    assert "responses: 0" in captured.out
    assert "Where should we start?" not in captured.out and "Where should we start?" not in captured.err


def test_offscreen_chat_is_found_by_scrolling_without_typing(tmp_path):
    html = (
        "<!-- synthetic fixture --><nav><a href='/scheduled'>Scheduled</a>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        f"<a href='/app/off1' data-offscreen='1'>{CHAT}</a></nav><main><model-response>"
        "27 Nov 2026\n| Link |\n| --- |\n| https://example.com/off |\n\nSources checked: 1"
        "</model-response></main>"
    )
    code, page = run(html, APP, tmp_path)
    assert code == 0 and page.typed == [] and page.sidebar_scrolled is True
    assert page.url.endswith("/app/off1")


def test_search_types_only_the_configured_title(tmp_path):
    html = (
        "<!-- synthetic fixture --><nav><a href='/scheduled'>Scheduled</a>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        "<button type='button'>Search chats</button>"
        "<input type='search' aria-label='Search chats'>"
        f"<a href='/app/sea1' data-search='1'>{CHAT}</a></nav><main><model-response>"
        "27 Nov 2026\n| Link |\n| --- |\n| https://example.com/sea |\n\nSources checked: 1"
        "</model-response></main>"
    )
    code, page = run(html, APP, tmp_path)
    assert code == 0
    assert page.typed == [CHAT]
    assert page.typed_on == ["input:Search chats:search"]
    assert page.url.endswith("/app/sea1")


def test_search_does_not_type_into_the_composer(tmp_path, capsys):
    html = (
        "<!-- synthetic fixture --><nav>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        "<a href='/app/ffff0000'>Some Other Chat</a>"
        "<button type='button'>Search chats</button>"
        "<textarea aria-label='Ask Gemini'></textarea></nav>"
    )
    code, page = run(html, APP, tmp_path)
    assert code == 4
    assert page.typed == []
    assert all(tag != "textarea" for tag, _name in page.clicks)
    assert "Ask Gemini" not in capsys.readouterr().err


def test_first_exact_chat_link_wins(tmp_path):
    html = (
        "<!-- synthetic fixture --><nav>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        f"<a href='/app/first'>{CHAT}</a>"
        f"<a href='/app/second'>{CHAT}</a></nav><main><model-response>"
        "Sources checked: 1</model-response></main>"
    )
    code, page = run(html, APP, tmp_path)
    assert code == 0 and page.url.endswith("/app/first")


def test_article_selector_is_used_when_custom_elements_are_absent(tmp_path, capsys):
    html = (
        "<!-- synthetic fixture --><nav>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        f"<a href='/app/art1'>{CHAT}</a></nav><main>"
        "<user-query>USERMARKER</user-query>"
        "<div role='article'>27 Nov 2026\n| Link |\n| --- |\n| https://example.com/art |\n\n"
        "Sources checked: 1</div></main>"
    )
    code, _page = run(html, APP, tmp_path)
    err = capsys.readouterr().err
    assert code == 0 and "selector: article" in err and "USERMARKER" not in err
    raw = (tmp_path / "2026-11-27-briefing.md").read_text(encoding="utf-8")
    assert "https://example.com/art" in raw and "USERMARKER" not in raw


def test_data_message_id_skips_user_author(tmp_path, capsys):
    html = (
        "<!-- synthetic fixture --><nav>"
        "<a href='https://accounts.google.com/'>Google Account: Synthetic</a>"
        f"<a href='/app/mid1'>{CHAT}</a></nav><main>"
        "<div data-message-id='u1' data-author='user'>| Link |\n| --- |\n| https://example.com/user |\n</div>"
        "<div data-message-id='m1' data-author='model'>27 Nov 2026\n| Link |\n| --- |\n"
        "| https://example.com/model |\n\nSources checked: 1</div></main>"
    )
    code, _page = run(html, APP, tmp_path)
    assert code == 0 and "selector: data-message-id" in capsys.readouterr().err
    raw = (tmp_path / "2026-11-27-briefing.md").read_text(encoding="utf-8")
    assert "https://example.com/model" in raw and "https://example.com/user" not in raw


def test_scheduled_with_no_tasks_exits_4(tmp_path, capsys):
    code, page = run(
        _html("synthetic_scheduled_empty.html"), APP, tmp_path,
        mode="scheduled", chats=[], titles=ACTIONS,
    )
    captured = capsys.readouterr()
    assert code == 4
    assert "none-found: no scheduled tasks" in captured.err
    assert "scheduled skipped: 4" in captured.out
    assert "Describe a task" not in captured.out and "Describe a task" not in captured.err
    assert page.gotos == []
    assert list(tmp_path.iterdir()) == []


def test_scheduled_hit_and_both_mode_skips_missing_titles(tmp_path, capsys):
    code, page = run(
        _html("synthetic_scheduled_hit.html"), APP, tmp_path,
        mode="scheduled", chats=[], titles=ACTIONS,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "scheduled skipped: 3" in captured.out
    assert ("button", "Latest") in page.clicks
    assert page.gotos == []
    saved = _saved(tmp_path, "2026-11-27-morning-scout")
    assert saved["action"] == "Morning scout"
    assert saved["rows"][0]["link"] == "https://example.com/sched"
    assert "https://example.com/sched" not in captured.out

    both = tmp_path / "both"
    both.mkdir()
    code, page = run(
        _html("synthetic_sidebar_with_chat.html"), APP, both,
        mode="both", titles=ACTIONS,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "scheduled skipped: 4" in captured.out
    assert ("a", CHAT) in page.clicks and ("a", "Scheduled") in page.clicks
    names = {p.name for p in both.iterdir()}
    assert "2026-11-27-briefing.json" in names
    assert "2026-11-27-morning-scout.json" not in names


def test_scheduled_probe_is_structure_only(tmp_path, capsys):
    code, page = run(
        _html("synthetic_scheduled_empty.html"), APP, tmp_path,
        mode="scheduled", chats=[], titles=ACTIONS, probe=True,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "path: /scheduled" in captured.out
    assert "Describe a task" not in captured.out
    assert 500 not in page.waits
    assert list(tmp_path.iterdir()) == []


def test_dry_run_writes_nothing(tmp_path, capsys):
    code, _page = run(_html("synthetic_sidebar_with_chat.html"), APP, tmp_path, dry_run=True)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == f"{CHAT}: 1 rows"
    assert "BODYMARKER" not in captured.out
    assert list(tmp_path.iterdir()) == []


def test_open_gemini_tab_is_not_navigated_with_goto(tmp_path):
    code, page = run(_html("synthetic_sidebar_with_chat.html"), "https://gemini.google.com/scheduled", tmp_path)
    assert code == 0 and page.gotos == []


# ── main() exit codes that do not need a page ───────────────────────────────
def test_main_exit_codes(monkeypatch, tmp_path, capsys):
    def boom_login(*_a, **_k):
        raise gf.NeedsLogin()

    monkeypatch.setattr(gf, "fetch_all", boom_login)
    assert gf.main(["--dry-run", "--inbox", str(tmp_path)]) == 3
    assert capsys.readouterr().err.strip() == "needs-login"

    def boom_fetch(*_a, **_k):
        raise gf.FetchError("cdp unreachable")

    monkeypatch.setattr(gf, "fetch_all", boom_fetch)
    assert gf.main(["--inbox", str(tmp_path)]) == 1
    assert capsys.readouterr().err.strip() == "gemini fetch failed: cdp unreachable"

    def boom_body(*_a, **_k):
        raise RuntimeError("PAGE BODY SECRET")

    monkeypatch.setattr(gf, "fetch_all", boom_body)
    assert gf.main(["--inbox", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err.strip() == "gemini fetch failed: error"
    assert "PAGE BODY SECRET" not in err

    monkeypatch.delenv("GEMINI_SOURCE", raising=False)
    bad = tmp_path / "bad.yaml"
    bad.write_text("source: [\n", encoding="utf-8")
    assert gf.main(["--config", str(bad)]) == 2
    assert capsys.readouterr().err.strip() == "bad config: invalid yaml"

    empty = tmp_path / "empty.yaml"
    empty.write_text("source: chat\nchats: []\n", encoding="utf-8")
    assert gf.main(["--config", str(empty)]) == 2
    assert capsys.readouterr().err.strip() == "bad config: no chats configured"

    no_actions = tmp_path / "no-actions.yaml"
    no_actions.write_text("source: scheduled\nactions: []\n", encoding="utf-8")
    assert gf.main(["--config", str(no_actions)]) == 2
    assert capsys.readouterr().err.strip() == "bad config: no actions configured"

    monkeypatch.setenv("GEMINI_SOURCE", "nope")
    assert gf.main(["--config", str(ROOT / "config" / "gemini_actions.yaml"), "--inbox", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.strip() == "bad config: GEMINI_SOURCE must be chat, scheduled, or both"
    assert "nope" not in err

    seen = {}

    def record(cdp, inbox, **kw):
        seen["cdp"] = cdp
        seen.update(kw)

    monkeypatch.setenv("GEMINI_SOURCE", "both")
    monkeypatch.setattr(gf, "fetch_all", record)
    assert gf.main(["--inbox", str(tmp_path), "--dry-run"]) == 0
    assert seen["mode"] == "both" and seen["dry_run"] is True and seen["probe"] is False
    assert seen["chats"] == [{"title": CHAT, "label": "briefing"}]
    assert seen["titles"] == ACTIONS


def test_box_maps_exit_3_and_4_and_stops(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.txt"
    (bindir / "python").write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{log}'\n"
        "case \"$*\" in\n"
        "  *gemini_fetch*) exit \"$FAKE_RC\" ;;\n"
        "esac\n"
        f"echo unexpected >> '{log}'\n"
        "exit 99\n",
        encoding="utf-8",
    )
    os.chmod(bindir / "python", 0o755)
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    for rc, needle in ((3, "gemini fetch failed: needs-login"), (4, "gemini fetch failed: none-found"),
                       (1, "gemini fetch failed: exit 1"), (5, "gemini fetch failed: exit 5")):
        log.write_text("", encoding="utf-8")
        env["FAKE_RC"] = str(rc)
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts" / "run_daily_box.sh")],
            cwd=str(ROOT), env=env, capture_output=True, text=True, check=False,
        )
        assert proc.returncode == rc
        assert needle in proc.stderr
        calls = log.read_text(encoding="utf-8").strip().splitlines()
        assert len(calls) == 1 and "gemini_fetch" in calls[0]
        assert "unexpected" not in calls[0]
