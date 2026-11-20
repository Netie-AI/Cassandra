"""WeLink posting: config, splitting, step engine (fake page), ledger, webhook (httpx stubbed). No browser, no network."""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager

import pytest

from src.briefing import welink

SECRET = "SECRETTOKEN123456"
URL = f"https://hooks.example.com/robot/send/{SECRET}?key=QUERYSECRET99"


# ── fakes ───────────────────────────────────────────────────────────────────────────────────────
class FakeKeyboard:
    def __init__(self, log):
        self.log = log

    def press(self, k):
        self.log.append(("kbd.press", k))

    def insert_text(self, t):
        self.log.append(("kbd.insert", t))


class FakeLocator:
    def __init__(self, page, sel):
        self.page, self.sel = page, sel

    def count(self):
        self.page.log.append(("count", self.sel))
        return self.page.counts.pop(0) if len(self.page.counts) > 1 else self.page.counts[0]


class FakePage:
    """Records every call. counts: successive locator().count() results (last one repeats)."""

    def __init__(self, counts=(0, 1), fail_on=None):
        self.log, self.counts, self.fail_on = [], list(counts), fail_on
        self.keyboard = FakeKeyboard(self.log)

    def _do(self, name, *a, **kw):
        self.log.append((name, *a))
        if self.fail_on == name:
            raise RuntimeError(f"{name} blew up\nsecond line")

    def goto(self, url, timeout=None):
        self._do("goto", url)

    def wait_for_selector(self, sel, timeout=None):
        self._do("wait_for", sel)

    def click(self, sel, timeout=None):
        self._do("click", sel)

    def fill(self, sel, val, timeout=None):
        self._do("fill", sel, val)

    def press(self, sel, key, timeout=None):
        self._do("press", sel, key)

    def evaluate(self, js, arg=None):
        self._do("evaluate", arg)

    def wait_for_timeout(self, ms):
        self.log.append(("sleep", ms))

    def locator(self, sel):
        return FakeLocator(self, sel)

    def screenshot(self, path=None):
        self.log.append(("screenshot", path))
        open(path, "wb").write(b"png")


def names(page):
    return [e[0] for e in page.log]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(welink, "_sleep", lambda s: None)
    return tmp_path


def browser_cfg(tmp, **over):
    b = {"url": "https://chat.example.com/", "profile_dir": str(tmp / "profile"), "ready": "#me",
         "sent_check": {"selector": 'ul .msg:has-text("{line}")', "timeout_ms": 600},
         "steps": [{"action": "click", "selector": "#search"},
                   {"action": "fill", "selector": "#search", "value": "{chat}"},
                   {"action": "click", "selector": 'li:has-text("{chat}")'},
                   {"action": "insert_text", "selector": "#ed", "value": "{message}"},
                   {"action": "press", "key": "Enter", "final": True}]}
    b.update(over)
    return b


def cfg(tmp, targets=None, **over):
    c = {"targets": {"ai": targets or [{"name": "t1", "transport": "browser", "chat": 'AI "Room"'}]},
         "browser": browser_cfg(tmp), "ledger": str(tmp / "sent.json"), "screenshot_dir": str(tmp / "shots"),
         "limits": {"min_interval_s": 0}}
    c.update(over)
    return c


@contextmanager
def patch_session(monkeypatch, page, opened=None):
    @contextmanager
    def sess(bcfg, headless=None):
        if opened is not None:
            opened.append(1)
        yield page
    monkeypatch.setattr(welink, "_browser_session", sess)
    yield


# ── config validation ───────────────────────────────────────────────────────────────────────────
def test_empty_targets_and_empty_config_are_valid():
    assert welink.validate_config({"targets": {}})["targets"] == {}
    assert welink.validate_config(None)["browser"] is None


@pytest.mark.parametrize("bad,needle", [
    ({"nope": 1}, "nope"),
    ({"targets": {"sms": []}}, "sms"),
    ({"targets": {"ai": [{"name": "a", "transport": "carrier-pigeon"}]}}, "carrier-pigeon"),
    ({"targets": {"ai": [{"name": "a", "transport": "webhook"}]}}, "url_env"),
    ({"targets": {"ai": [{"name": "a", "transport": "webhook", "url_env": "https://x/y"}]}}, "never a URL"),
    ({"targets": {"ai": [{"name": "a", "transport": "browser"}]}}, "chat"),
    ({"targets": {"ai": [{"name": "a", "transport": "webhook", "url_env": "E", "bogus": 1}]}}, "bogus"),
    ({"targets": {"ai": [{"name": "a", "transport": "webhook", "url_env": "E"},
                         {"name": "a", "transport": "webhook", "url_env": "E"}]}}, "duplicate"),
    ({"limits": {"max_message_chars": 5}}, "max_message_chars"),
    ({"limits": {"surprise": 1}}, "surprise"),
    ({"webhook": {"method": "GET"}}, "method"),
])
def test_bad_config_names_the_problem(bad, needle):
    with pytest.raises(ValueError, match=needle):
        welink.validate_config(bad)


def test_browser_config_errors(tmp_path):
    t = [{"name": "a", "transport": "browser", "chat": "C"}]
    good = browser_cfg(tmp_path)
    cases = [
        ({"url": None}, "browser.url"),
        ({"steps": [{"action": "teleport"}]}, "teleport"),
        ({"steps": [{"action": "click"}]}, "selector"),
        ({"steps": [{"action": "click", "selector": "x", "oops": 1}]}, "oops"),
        ({"steps": [{"action": "click", "selector": "x"}]}, "final"),
        ({"sent_check": {"selector": "no placeholder"}}, "{line}"),
        ({"profile_dir": str(welink.ROOT / "profile")}, "outside the repository"),
        ({"mystery": 1}, "mystery"),
    ]
    for over, needle in cases:
        b = {**good, **over}
        if over.get("url", 1) is None:
            b.pop("url")
        with pytest.raises(ValueError, match=needle.replace("{", r"\{").replace("}", r"\}")):
            welink.validate_config({"targets": {"ai": t}, "browser": b})
    with pytest.raises(ValueError, match="browser.url"):                 # browser target but no browser section
        welink.validate_config({"targets": {"ai": t}})


# ── splitting ───────────────────────────────────────────────────────────────────────────────────
def test_split_short_and_empty():
    assert welink.split_message("  hi\nthere ", 100) == ["hi\nthere"]
    assert welink.split_message("   ", 100) == []


def test_split_at_blank_lines_never_mid_line():
    text = "\n\n".join(f"para {i} " + "x" * 20 for i in range(6))
    parts = welink.split_message(text, 70)
    assert len(parts) > 1 and all(len(p) <= 70 for p in parts)
    assert "\n\n".join(parts) == text


def test_split_long_paragraph_falls_back_to_lines_then_hard_splits():
    lines = [f"line{i} " + "y" * 10 for i in range(8)]
    parts = welink.split_message("\n".join(lines), 50)
    assert all(len(p) <= 50 for p in parts) and "\n".join(parts) == "\n".join(lines)
    hard = welink.split_message("z" * 250, 100)
    assert [len(p) for p in hard] == [100, 100, 50]


# ── step engine ─────────────────────────────────────────────────────────────────────────────────
def test_steps_run_in_order_with_placeholders_and_line_breaks(tmp_path):
    b = welink.validate_config(cfg(tmp_path))["browser"]
    page = FakePage()
    welink.run_steps(page, b, {"chat": 'AI "Room"', "message": "a\nb\nc"})
    assert page.log == [
        ("click", "#search"), ("fill", "#search", 'AI "Room"'),
        ("click", 'li:has-text("AI \\"Room\\"")'),                 # quotes escaped inside selectors only
        ("click", "#ed"), ("kbd.insert", "a"), ("kbd.press", "Shift+Enter"), ("kbd.insert", "b"),
        ("kbd.press", "Shift+Enter"), ("kbd.insert", "c"), ("kbd.press", "Enter")]


def test_all_actions_work(tmp_path):
    steps = [{"action": "goto"}, {"action": "wait_for", "selector": "#a"}, {"action": "sleep", "ms": 5},
             {"action": "paste", "selector": "#ed"}, {"action": "press", "selector": "#ed", "key": "Tab", "final": True}]
    b = welink.validate_config(cfg(tmp_path, browser=browser_cfg(tmp_path, steps=steps)))["browser"]
    page = FakePage()
    welink.run_steps(page, b, {"chat": "C", "message": "m"})
    assert page.log == [("goto", "https://chat.example.com/"), ("wait_for", "#a"), ("sleep", 5), ("click", "#ed"),
                        ("evaluate", "m"), ("press", "#ed", "Tab")]


def test_step_failure_reports_index_and_stops(tmp_path):
    b = welink.validate_config(cfg(tmp_path))["browser"]
    page = FakePage(fail_on="fill")
    with pytest.raises(welink.StepError) as ei:
        welink.run_steps(page, b, {"chat": "C", "message": "m"})
    assert ei.value.index == 1 and "fill" in str(ei.value) and "second line" not in str(ei.value)
    assert names(page) == ["click", "fill"]                          # nothing after the failure ran


def test_optional_step_failure_is_ignored(tmp_path):
    steps = [{"action": "click", "selector": "#popup", "optional": True}, {"action": "press", "key": "Enter", "final": True}]
    b = welink.validate_config(cfg(tmp_path, browser=browser_cfg(tmp_path, steps=steps)))["browser"]
    page = FakePage(fail_on="click")
    welink.run_steps(page, b, {"chat": "C", "message": "m"})
    assert names(page) == ["click", "kbd.press"]


def test_probe_mode_stops_before_the_send_action(tmp_path):
    b = welink.validate_config(cfg(tmp_path))["browser"]
    page = FakePage()
    welink.run_steps(page, b, {"chat": "C", "message": "m"}, stop_before_final=True)
    assert ("kbd.press", "Enter") not in page.log and ("kbd.insert", "m") in page.log


# ── sent_check, ledger, deliver ─────────────────────────────────────────────────────────────────
def test_confirmed_send_writes_ledger_and_checks_the_distinctive_line(env, monkeypatch):
    page = FakePage(counts=(2, 3))                                      # count rises 2 -> 3 after the send
    with patch_session(monkeypatch, page):
        out = welink.deliver([{"channel": "ai", "messages": ["short\nthe longest line of all\nx"]}], cfg(env),
                             dry_run=False, log=lambda s: None)
    assert (out["sent"], out["failed"]) == (1, 0)
    counted = [e[1] for e in page.log if e[0] == "count"]
    assert counted[0] == 'ul .msg:has-text("the longest line of all")'
    assert welink._key("t1", "short\nthe longest line of all\nx") in welink._ledger_load(env / "sent.json")


def test_sent_check_failure_is_failed_with_screenshot_and_no_ledger(env, monkeypatch):
    page = FakePage(counts=(1,))                                        # never rises: old identical message only
    with patch_session(monkeypatch, page):
        out = welink.deliver([{"channel": "ai", "messages": ["hello"]}], cfg(env), dry_run=False, log=lambda s: None)
    assert (out["sent"], out["failed"]) == (0, 1)
    detail = out["details"][0]
    assert "sent_check" in detail and "shots" in detail and ".png" in detail
    assert list((env / "shots").glob("fail-t1-*.png"))
    assert not (env / "sent.json").exists()


def test_step_failure_during_deliver_is_failed_not_raised(env, monkeypatch):
    page = FakePage(fail_on="click")
    with patch_session(monkeypatch, page):
        out = welink.deliver([{"channel": "ai", "messages": ["hello"]}], cfg(env), dry_run=False, log=lambda s: None)
    assert out["failed"] == 1 and "step 0" in out["details"][0]


def test_ledger_skips_within_20h_and_resends_after(env, monkeypatch):
    page = FakePage(counts=(0, 1))
    now = [dt.datetime(2026, 1, 1, 12, tzinfo=dt.timezone.utc)]
    monkeypatch.setattr(welink, "_now", lambda: now[0])
    batches = [{"channel": "ai", "messages": ["hello"]}]
    opened = []
    with patch_session(monkeypatch, page, opened):
        assert welink.deliver(batches, cfg(env), dry_run=False, log=lambda s: None)["sent"] == 1
        now[0] += dt.timedelta(hours=19, minutes=59)
        out = welink.deliver(batches, cfg(env), dry_run=False, log=lambda s: None)
        assert (out["sent"], out["skipped"]) == (0, 1) and len(opened) == 1      # no browser for a pure skip
        now[0] += dt.timedelta(minutes=2)
        page.counts = [0, 1]
        out = welink.deliver(batches, cfg(env), dry_run=False, log=lambda s: None)
        assert out["sent"] == 1 and out["skipped"] == 0


def test_ledger_key_is_per_target(env, monkeypatch):
    welink._ledger_add(env / "sent.json", welink._key("t1", "hello"))
    ledger = welink._ledger_load(env / "sent.json")
    assert welink._ledger_recent(ledger, welink._key("t1", "hello"))
    assert not welink._ledger_recent(ledger, welink._key("t2", "hello"))


def test_dry_run_touches_nothing(env, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not be called in dry-run")
    monkeypatch.setattr(welink, "_browser_session", boom)
    monkeypatch.setattr(welink.httpx, "request", boom)
    monkeypatch.setenv("HOOK", URL)
    c = cfg(env, targets=[{"name": "t1", "transport": "browser", "chat": "C"},
                          {"name": "w", "transport": "webhook", "url_env": "HOOK"}])
    out = welink.deliver([{"channel": "ai", "messages": ["x" * 200]}], c, dry_run=True, log=lambda s: None)
    assert (out["sent"], out["skipped"], out["failed"]) == (0, 0, 0) and len(out["details"]) == 2
    assert "('" + "x" * 80 + "'" in out["details"][0] or "x" * 80 in out["details"][0]
    assert "200 chars" in out["details"][0] and SECRET not in " ".join(out["details"])
    assert not (env / "sent.json").exists()


def test_max_messages_per_run_enforced(env, monkeypatch):
    page = FakePage(counts=(0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5))
    c = cfg(env, limits={"min_interval_s": 0, "max_messages_per_run": 2, "max_message_chars": 50})
    msg = "\n\n".join(f"paragraph number {i} with filler" for i in range(5))      # ~5 chunks of <=50
    with patch_session(monkeypatch, page):
        out = welink.deliver([{"channel": "ai", "messages": [msg]}], c, dry_run=False, log=lambda s: None)
    assert out["sent"] == 2 and out["failed"] >= 1
    assert any("max_messages_per_run" in d for d in out["details"])


def test_min_interval_between_sends(env, monkeypatch):
    sleeps = []
    monkeypatch.setattr(welink, "_sleep", sleeps.append)
    page = FakePage(counts=(0, 1))
    c = cfg(env, limits={"min_interval_s": 7})
    with patch_session(monkeypatch, page):
        welink.deliver([{"channel": "ai", "messages": ["one", "two"]}], c, dry_run=False, log=lambda s: None)
    assert sleeps == [7]


def test_channel_without_targets_is_skipped_not_failed(env):
    out = welink.deliver([{"channel": "markets", "messages": ["hi"]}], cfg(env), dry_run=False, log=lambda s: None)
    assert (out["sent"], out["skipped"], out["failed"]) == (0, 1, 0)


def test_empty_targets_config_delivers_nothing(env):
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], {"targets": {}, "ledger": str(env / "l.json")},
                         dry_run=False, log=lambda s: None)
    assert out["failed"] == 0 and out["sent"] == 0


def test_deliver_raises_valueerror_on_bad_config():
    with pytest.raises(ValueError):
        welink.deliver([], {"targets": {"ai": [{"name": "a", "transport": "x"}]}}, dry_run=True)


def test_missing_playwright_is_a_failure_with_instruction(env, monkeypatch):
    import builtins
    real = builtins.__import__

    def no_pw(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_pw)
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], cfg(env), dry_run=False, log=lambda s: None)
    assert out["failed"] == 1 and "pip install playwright" in out["details"][0]


# ── webhook ─────────────────────────────────────────────────────────────────────────────────────
class Resp:
    def __init__(self, status=200, body='{"code":"0"}'):
        self.status_code, self.text = status, body

    def json(self):
        import json
        return json.loads(self.text)


def wh_cfg(env):
    return {"targets": {"ai": [{"name": "bot", "transport": "webhook", "url_env": "HOOK"}]},
            "ledger": str(env / "sent.json"), "limits": {"min_interval_s": 0}}


def test_webhook_payload_shape_and_success(env, monkeypatch):
    monkeypatch.setenv("HOOK", URL)
    seen = {}

    def fake(method, url, **kw):
        seen.update(method=method, url=url, **kw)
        return Resp()
    monkeypatch.setattr(welink.httpx, "request", fake)
    out = welink.deliver([{"channel": "ai", "messages": ["line1\nline2"]}], wh_cfg(env), dry_run=False, log=lambda s: None)
    assert (out["sent"], out["failed"]) == (1, 0)
    assert seen["method"] == "POST" and seen["url"] == URL
    body = seen["json"]
    assert body["messageType"] == "text" and body["content"] == {"text": "line1\nline2"}
    assert isinstance(body["timeStamp"], int) and body["uuid"] and body["isAtAll"] is False


@pytest.mark.parametrize("resp", [Resp(500, "boom"), Resp(200, '{"code":"1001","msg":"bad"}'), Resp(200, "not json"),
                                  Resp(200, "{}")])
def test_webhook_failures_and_no_ledger(env, monkeypatch, resp):
    monkeypatch.setenv("HOOK", URL)
    monkeypatch.setattr(welink.httpx, "request", lambda *a, **k: resp)
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], wh_cfg(env), dry_run=False, log=lambda s: None)
    assert (out["sent"], out["failed"]) == (0, 1)
    assert not (env / "sent.json").exists()


def test_webhook_missing_env_var_fails_cleanly(env, monkeypatch):
    monkeypatch.delenv("HOOK", raising=False)
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], wh_cfg(env), dry_run=False, log=lambda s: None)
    assert out["failed"] == 1 and "HOOK is not set" in out["details"][0]


def test_token_never_appears_in_details_logs_or_errors(env, monkeypatch):
    monkeypatch.setenv("HOOK", URL)
    logged = []

    def exploding(method, url, **kw):
        raise welink.httpx.ConnectError(f"cannot connect to {url}")        # str() of this contains the URL
    monkeypatch.setattr(welink.httpx, "request", exploding)
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], wh_cfg(env), dry_run=False, log=logged.append)
    blob = " ".join(out["details"] + logged)
    assert out["failed"] == 1 and "ConnectError" in blob
    for s in (SECRET, "QUERYSECRET99", "hooks.example.com"):
        assert s not in blob

    echo = f"error for {URL} token {SECRET}"                              # a server echoing the URL back
    monkeypatch.setattr(welink.httpx, "request", lambda *a, **k: Resp(400, echo))
    out = welink.deliver([{"channel": "ai", "messages": ["hi"]}], wh_cfg(env), dry_run=False, log=logged.append)
    assert SECRET not in " ".join(out["details"]) and "QUERYSECRET99" not in " ".join(out["details"])


def test_mask_helper():
    assert SECRET not in welink._mask(f"x {URL} y {SECRET}", URL)
