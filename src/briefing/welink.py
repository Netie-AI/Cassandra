"""Post plain-text messages into WeLink chats.

    deliver(batches, cfg, *, dry_run, log=print) -> {"sent", "skipped", "failed", "details"}

Two transports, chosen per target in config/welink.yaml (see config/welink.example.yaml):
  webhook  HTTP POST to a group-robot URL read from an environment variable.
  browser  Playwright drives the owner's own logged-in WeLink web session through a YAML step list.

VERIFICATION STATUS (read this before trusting anything):
  * The step engine, splitting, ledger, sent_check and CLI are tested against a local mock page only.
  * UNVERIFIED against real WeLink: the web client URL, every selector in DEFAULT_STEPS and
    DEFAULT_SENT_CHECK, the webhook payload shape, the webhook success response, the message size limit.
    No official WeLink document for any of these could be fetched when this was written.
  * Nothing here was run against a real WeLink account.

CLI:  python -m src.briefing.welink login | probe --chat NAME | send --chat NAME --text "..." --yes
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHANNELS = ("ai", "markets")
LEDGER_WINDOW_H = 20
ACTIONS = ("goto", "wait_for", "click", "fill", "insert_text", "press", "paste", "sleep")
_sleep = time.sleep          # patched in tests
_now = lambda: dt.datetime.now(dt.timezone.utc)   # noqa: E731  (patched in tests)

# UNVERIFIED: best guess at a WeLink web chat. Replace via `python -m playwright codegen <url>`.
DEFAULT_STEPS = [
    {"action": "click", "selector": 'input[type="search"], [placeholder*="Search" i]'},
    {"action": "fill", "selector": 'input[type="search"], [placeholder*="Search" i]', "value": "{chat}"},
    {"action": "click", "selector": 'text="{chat}"'},
    {"action": "click", "selector": '[contenteditable="true"]'},
    {"action": "insert_text", "selector": '[contenteditable="true"]', "value": "{message}"},
    {"action": "press", "key": "Enter", "final": True},
]
# UNVERIFIED selector. {line} is a distinctive line of the sent chunk. Must be scoped to the message list,
# never to the editor, or an unsent draft would count as sent.
DEFAULT_SENT_CHECK = {"selector": '[class*="message"]:has-text("{line}")', "timeout_ms": 10000}
# UNVERIFIED payload and success rule. No official WeLink webhook document was found.
DEFAULT_PAYLOAD = {"messageType": "text", "content": {"text": "{message}"}, "timeStamp": "{timestamp_ms}",
                   "uuid": "{uuid}", "isAt": False, "isAtAll": False}
DEFAULT_SUCCESS = {"field": "code", "ok": [0, "0", 200, "200"]}


# ── config ────────────────────────────────────────────────────────────────────────────────────────
def _keys(d, allowed, where):
    if not isinstance(d, dict):
        raise ValueError(f"{where} must be a mapping")
    bad = sorted(set(d) - set(allowed))
    if bad:
        raise ValueError(f"unknown key(s) in {where}: {', '.join(map(str, bad))}")


def _num(d, key, default, where, lo=0):
    v = d.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < lo:
        raise ValueError(f"{where}.{key} must be a number >= {lo}")
    return v


def _validate_step(i, st):
    where = f"browser.steps[{i}]"
    _keys(st, ("action", "selector", "value", "key", "ms", "url", "final", "optional", "timeout_ms"), where)
    act = st.get("action")
    if act not in ACTIONS:
        raise ValueError(f"{where}: unknown action {act!r} (allowed: {', '.join(ACTIONS)})")
    need = {"goto": (), "wait_for": ("selector",), "click": ("selector",), "fill": ("selector", "value"),
            "insert_text": ("selector",), "press": ("key",), "paste": ("selector",), "sleep": ("ms",)}[act]
    for k in need:
        if k not in st:
            raise ValueError(f"{where}: action {act!r} needs {k!r}")
    return dict(st)


def validate_config(cfg) -> dict:
    """Return a normalised copy of cfg or raise ValueError naming the problem. {} and targets: {} are valid."""
    cfg = {} if cfg is None else cfg
    _keys(cfg, ("targets", "browser", "webhook", "limits", "ledger", "screenshot_dir"), "config")
    targets = cfg.get("targets") or {}
    _keys(targets, CHANNELS, "targets")
    out_targets, names = {}, set()
    for ch, lst in targets.items():
        if not isinstance(lst, list):
            raise ValueError(f"targets.{ch} must be a list")
        out_targets[ch] = []
        for t in lst:
            _keys(t, ("name", "transport", "url_env", "chat"), f"targets.{ch}[]")
            name = t.get("name")
            if not name or not isinstance(name, str):
                raise ValueError(f"targets.{ch}[]: every target needs a name")
            if name in names:
                raise ValueError(f"duplicate target name {name!r}")
            names.add(name)
            tr = t.get("transport")
            if tr == "webhook":
                if not isinstance(t.get("url_env"), str) or not t["url_env"]:
                    raise ValueError(f"target {name!r}: webhook needs url_env (an environment variable NAME)")
                if "://" in t["url_env"] or "chat" in t:
                    raise ValueError(f"target {name!r}: url_env must be a variable name, never a URL; chat is browser-only")
            elif tr == "browser":
                if not isinstance(t.get("chat"), str) or not t["chat"].strip():
                    raise ValueError(f"target {name!r}: browser needs chat")
                if "url_env" in t:
                    raise ValueError(f"target {name!r}: url_env is webhook-only")
            else:
                raise ValueError(f"target {name!r}: unknown transport {tr!r} (webhook or browser)")
            out_targets[ch].append(dict(t))

    lim = cfg.get("limits") or {}
    _keys(lim, ("max_message_chars", "max_messages_per_run", "min_interval_s"), "limits")
    limits = {"max_message_chars": int(_num(lim, "max_message_chars", 2000, "limits", 50)),
              "max_messages_per_run": int(_num(lim, "max_messages_per_run", 6, "limits", 1)),
              "min_interval_s": _num(lim, "min_interval_s", 3, "limits")}

    wh = cfg.get("webhook") or {}
    _keys(wh, ("method", "headers", "payload", "success", "timeout_s"), "webhook")
    suc = wh.get("success", DEFAULT_SUCCESS)
    _keys(suc, ("field", "ok"), "webhook.success")
    method = str(wh.get("method", "POST")).upper()
    if method not in ("POST", "PUT"):
        raise ValueError("webhook.method must be POST or PUT")
    webhook = {"method": method, "headers": dict(wh.get("headers") or {}),
               "payload": wh.get("payload", DEFAULT_PAYLOAD), "success": {"field": suc.get("field"), "ok": list(suc.get("ok", []))},
               "timeout_s": _num(wh, "timeout_s", 15, "webhook", 1)}
    if not isinstance(webhook["payload"], dict):
        raise ValueError("webhook.payload must be a mapping")

    browser = None
    if any(t["transport"] == "browser" for lst in out_targets.values() for t in lst) or cfg.get("browser"):
        b = cfg.get("browser") or {}
        _keys(b, ("url", "profile_dir", "browser_channel", "executable_path", "args", "headless", "ready", "steps",
                  "sent_check", "timeouts"), "browser")
        for k in ("url", "ready"):
            if not isinstance(b.get(k), str) or not b[k]:
                raise ValueError(f"browser.{k} is required")
        steps = b.get("steps") or DEFAULT_STEPS
        if not isinstance(steps, list) or not steps:
            raise ValueError("browser.steps must be a non-empty list")
        steps = [_validate_step(i, s) for i, s in enumerate(steps)]
        if sum(1 for s in steps if s.get("final")) != 1:
            raise ValueError("browser.steps needs exactly one step with final: true (the send action)")
        sc = b.get("sent_check") or DEFAULT_SENT_CHECK
        _keys(sc, ("selector", "timeout_ms"), "browser.sent_check")
        if "{line}" not in str(sc.get("selector", "")):
            raise ValueError("browser.sent_check.selector must contain {line}")
        to = b.get("timeouts") or {}
        _keys(to, ("step_ms", "ready_ms"), "browser.timeouts")
        profile = Path(os.path.expanduser(b.get("profile_dir") or "~/.cassandra/welink-profile")).resolve()
        if profile == ROOT or ROOT in profile.parents:
            raise ValueError("browser.profile_dir must be outside the repository (it holds login cookies)")
        browser = {"url": b["url"], "profile_dir": str(profile), "browser_channel": b.get("browser_channel"),
                   "executable_path": b.get("executable_path"), "args": list(b.get("args") or []),
                   "headless": bool(b.get("headless", False)), "ready": b["ready"], "steps": steps,
                   "sent_check": {"selector": sc["selector"], "timeout_ms": int(sc.get("timeout_ms", 10000))},
                   "step_ms": int(_num(to, "step_ms", 8000, "browser.timeouts", 100)),
                   "ready_ms": int(_num(to, "ready_ms", 30000, "browser.timeouts", 100))}

    def _path(v, default):
        p = Path(v or default)
        return p if p.is_absolute() else ROOT / p
    return {"targets": out_targets, "limits": limits, "webhook": webhook, "browser": browser,
            "ledger": _path(cfg.get("ledger"), "reports/welink/sent.json"),
            "screenshot_dir": _path(cfg.get("screenshot_dir"), "reports/welink")}


# ── splitting and ledger ──────────────────────────────────────────────────────────────────────────
def _pack(parts: list[str], sep: str, limit: int) -> list[str]:
    out, cur = [], ""
    for p in parts:
        joined = f"{cur}{sep}{p}" if cur else p
        if len(joined) <= limit:
            cur = joined
        else:
            if cur:
                out.append(cur)
            cur = p
    return out + [cur] if cur else out


def split_message(text: str, limit: int) -> list[str]:
    """Split at blank lines, never mid-line; a single line longer than limit is hard-split."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks, cur = [], []                         # cur: consecutive paragraphs that fit
    for para in text.split("\n\n"):
        if len(para) <= limit:
            cur.append(para)
            continue
        chunks += _pack(cur, "\n\n", limit)
        cur = []
        lines = [ln[i:i + limit] for ln in para.split("\n") for i in range(0, max(len(ln), 1), limit)]
        chunks += _pack(lines, "\n", limit)
    return chunks + _pack(cur, "\n\n", limit)


def _key(target: str, message: str) -> str:
    return hashlib.sha256(f"{target}\0{message}".encode("utf-8")).hexdigest()


def _ledger_load(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ledger_recent(ledger: dict, key: str) -> bool:
    try:
        ts = dt.datetime.fromisoformat(ledger[key])
    except (KeyError, ValueError, TypeError):
        return False
    return _now() - ts < dt.timedelta(hours=LEDGER_WINDOW_H)


def _ledger_add(path: Path, key: str) -> None:
    ledger = _ledger_load(path)
    ledger[key] = _now().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=0), encoding="utf-8")
    os.replace(tmp, path)


# ── webhook transport ─────────────────────────────────────────────────────────────────────────────
def _fill(obj, vals):
    if isinstance(obj, str):
        for k, v in vals.items():
            if obj == "{" + k + "}":
                return v                        # whole-string placeholder keeps the value's type
        for k, v in vals.items():
            obj = obj.replace("{" + k + "}", str(v))
        return obj
    if isinstance(obj, dict):
        return {k: _fill(v, vals) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fill(v, vals) for v in obj]
    return obj


def build_payload(template: dict, message: str) -> dict:
    return _fill(template, {"message": message, "uuid": uuid.uuid4().hex, "timestamp_ms": int(_now().timestamp() * 1000)})


def _mask(text: str, url: str) -> str:
    u = urlsplit(url)
    bits = {url, u.netloc + u.path} | {s for s in u.path.split("/") if len(s) >= 6} | {v for _, v in parse_qsl(u.query) if len(v) >= 4}
    for b in sorted(bits, key=len, reverse=True):
        text = text.replace(b, "***")
    return text


def _send_webhook(target: dict, wcfg: dict, message: str) -> tuple[bool, str]:
    url = os.environ.get(target["url_env"], "")
    if not url:
        return False, f"environment variable {target['url_env']} is not set"
    try:
        r = httpx.request(wcfg["method"], url, json=build_payload(wcfg["payload"], message),
                          headers=wcfg["headers"], timeout=wcfg["timeout_s"])
    except Exception as e:                      # str(e) can contain the URL, so only the type is reported
        return False, f"request failed ({type(e).__name__})"
    body = _mask((r.text or "")[:120].replace("\n", " "), url)
    if not 200 <= r.status_code < 300:
        return False, f"HTTP {r.status_code}: {body}"
    field = wcfg["success"]["field"]
    if field is None:
        return True, f"HTTP {r.status_code}"
    try:
        val = r.json()[field]
    except Exception:
        return False, f"HTTP {r.status_code} but response has no {field!r}: {body}"
    if str(val) in {str(x) for x in wcfg["success"]["ok"]}:
        return True, f"HTTP {r.status_code} {field}={val}"
    return False, f"HTTP {r.status_code} {field}={val}: {body}"


# ── browser transport: the step engine ────────────────────────────────────────────────────────────
class StepError(Exception):
    def __init__(self, index, step, why):
        super().__init__(f"step {index} ({step.get('action')} {step.get('selector', '')}): {why}")
        self.index, self.step = index, step


def _sel(s: str, **vals) -> str:
    """Substitute placeholders into a selector; quotes and backslashes are escaped for use inside "..."."""
    for k, v in vals.items():
        s = s.replace("{" + k + "}", str(v).replace("\\", "\\\\").replace('"', '\\"'))
    return s


def _val(s: str, **vals) -> str:
    for k, v in vals.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def run_step(page, st: dict, vals: dict, bcfg: dict) -> None:
    act, t = st["action"], st.get("timeout_ms", bcfg["step_ms"])
    sel = _sel(st["selector"], **vals) if "selector" in st else None
    if act == "goto":
        page.goto(_val(st.get("url", bcfg["url"]), **vals), timeout=t)
    elif act == "wait_for":
        page.wait_for_selector(sel, timeout=t)
    elif act == "click":
        page.click(sel, timeout=t)
    elif act == "fill":
        page.fill(sel, _val(st["value"], **vals), timeout=t)
    elif act == "insert_text":                  # no Enter pressed; line breaks become Shift+Enter
        page.click(sel, timeout=t)
        for i, line in enumerate(_val(st.get("value", "{message}"), **vals).split("\n")):
            if i:
                page.keyboard.press("Shift+Enter")
            if line:
                page.keyboard.insert_text(line)
    elif act == "press":
        page.press(sel, st["key"], timeout=t) if sel else page.keyboard.press(st["key"])
    elif act == "paste":                        # synthetic paste event carrying text/plain, no OS clipboard needed
        page.click(sel, timeout=t)
        page.evaluate("""text => { const el = document.activeElement; const dt = new DataTransfer();
            dt.setData('text/plain', text);
            el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""",
                      _val(st.get("value", "{message}"), **vals))
    elif act == "sleep":
        page.wait_for_timeout(st["ms"])


def run_steps(page, bcfg: dict, vals: dict, *, before_final=None, stop_before_final=False) -> None:
    """Run the steps in order. before_final() is called just before the send step. Raises StepError."""
    for i, st in enumerate(bcfg["steps"]):
        if st.get("final"):
            if stop_before_final:
                return
            if before_final:
                before_final()
        try:
            run_step(page, st, vals, bcfg)
        except Exception as e:
            if st.get("optional"):
                continue
            raise StepError(i, st, (str(e).splitlines() or [type(e).__name__])[0][:200]) from None


def _distinct_line(chunk: str) -> str:
    return max((ln.strip() for ln in chunk.split("\n")), key=len)[:60]


def _screenshot(page, d: Path, name: str) -> str:
    p = d / f"{name}-{_now().strftime('%Y%m%dT%H%M%S')}.png"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(p))
        return str(p)
    except Exception:
        return "(screenshot failed)"


def send_browser(page, bcfg: dict, shot_dir: Path, target_name: str, chat: str, chunk: str) -> tuple[bool, str]:
    """Run the steps for one chunk, then confirm it appears in the conversation (count must rise)."""
    check = _sel(bcfg["sent_check"]["selector"], line=_distinct_line(chunk))
    base = []
    vals = {"chat": chat, "message": chunk}
    try:
        run_steps(page, bcfg, vals, before_final=lambda: base.append(page.locator(check).count()))
        deadline = _now() + dt.timedelta(milliseconds=bcfg["sent_check"]["timeout_ms"])
        while True:
            if page.locator(check).count() > (base[0] if base else 0):
                return True, "confirmed in conversation"
            if _now() >= deadline:
                break
            page.wait_for_timeout(250)
        why = "sent_check not satisfied: message not seen in the conversation"
    except StepError as e:
        why = str(e)
    return False, f"{why}; screenshot {_screenshot(page, shot_dir, 'fail-' + target_name)}"


@contextlib.contextmanager
def _browser_session(bcfg: dict, headless=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright is not installed. Run: pip install playwright "
                           "(no browser download needed if browser_channel is msedge or chrome)") from None
    with sync_playwright() as pw:
        kw = {"headless": bcfg["headless"] if headless is None else headless, "args": bcfg["args"]}
        if bcfg["executable_path"]:
            kw["executable_path"] = bcfg["executable_path"]
        elif bcfg["browser_channel"]:
            kw["channel"] = bcfg["browser_channel"]
        ctx = pw.chromium.launch_persistent_context(bcfg["profile_dir"], **kw)
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            ctx.close()


def _open_ready(page, bcfg: dict, shot_dir: Path) -> None:
    try:
        page.goto(bcfg["url"], timeout=bcfg["ready_ms"])
        page.wait_for_selector(bcfg["ready"], timeout=bcfg["ready_ms"])
    except Exception as e:
        raise RuntimeError(f"not logged in or page did not load ({(str(e).splitlines() or [''])[0][:100]}); "
                           f"run `python -m src.briefing.welink login`; screenshot {_screenshot(page, shot_dir, 'notready')}") from None


# ── deliver ───────────────────────────────────────────────────────────────────────────────────────
def deliver(batches, cfg, *, dry_run, log=print) -> dict:
    c = validate_config(cfg)
    lim, res = c["limits"], {"sent": 0, "skipped": 0, "failed": 0, "details": []}

    def note(kind, line):
        res[kind] += 1 if kind != "details" else 0
        res["details"].append(line)

    stack, page, page_err = contextlib.ExitStack(), None, None
    ledger = _ledger_load(c["ledger"])
    first_send = True
    with stack:
        for batch in batches:
            ch = batch["channel"]
            chunks = [p for m in batch["messages"] for p in split_message(m, lim["max_message_chars"])]
            targets = c["targets"].get(ch, [])
            if not targets:
                for _ in chunks:
                    note("skipped", f"{ch}: no targets configured")
                continue
            for t in targets:
                for n, chunk in enumerate(chunks, 1):
                    tag = f"{t['name']} [{n}/{len(chunks)}]"
                    if dry_run:
                        res["details"].append(f"DRY RUN {tag} via {t['transport']}: {chunk[:80]!r} ({len(chunk)} chars)")
                        continue
                    if n > lim["max_messages_per_run"]:
                        note("failed", f"{tag}: not sent, max_messages_per_run={lim['max_messages_per_run']} reached")
                        continue
                    key = _key(t["name"], chunk)
                    if _ledger_recent(ledger, key):
                        note("skipped", f"{tag}: already sent in the last {LEDGER_WINDOW_H}h")
                        continue
                    if not first_send:
                        _sleep(lim["min_interval_s"])
                    first_send = False
                    if t["transport"] == "webhook":
                        ok, why = _send_webhook(t, c["webhook"], chunk)
                    else:
                        if page is None and page_err is None:
                            try:
                                page = stack.enter_context(_browser_session(c["browser"]))
                                _open_ready(page, c["browser"], c["screenshot_dir"])
                            except Exception as e:
                                page_err = f"browser unavailable: {e}"
                        if page_err:
                            ok, why = False, page_err
                        else:
                            ok, why = send_browser(page, c["browser"], c["screenshot_dir"], t["name"], t["chat"], chunk)
                    if ok:
                        _ledger_add(c["ledger"], key)           # only after a confirmed send
                        ledger[key] = _now().isoformat()
                        note("sent", f"{tag}: sent ({why})")
                    else:
                        note("failed", f"{tag}: FAILED {why}")
    for line in res["details"]:
        log(line)
    return res


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────
def _browser_cfg(path: str) -> dict:
    c = validate_config(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    if not c["browser"]:
        raise SystemExit("config has no browser section")
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.briefing.welink")
    ap.add_argument("--config", default=str(ROOT / "config" / "welink.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("probe").add_argument("--chat", required=True)
    s = sub.add_parser("send")
    s.add_argument("--chat", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--yes", action="store_true", help="required: really send")
    a = ap.parse_args(argv)
    c = _browser_cfg(a.config)
    b, shots = c["browser"], c["screenshot_dir"]

    if a.cmd == "send" and not a.yes:
        print("refusing to send without --yes", file=sys.stderr)
        return 2
    try:
        with _browser_session(b, headless=False if a.cmd == "login" else None) as page:
            if a.cmd == "login":
                import threading
                done = threading.Event()
                threading.Thread(target=lambda: (input("Log in in the browser, then press Enter here (or wait)...\n"), done.set()),
                                 daemon=True).start()
                page.goto(b["url"])
                while not done.is_set() and page.locator(b["ready"]).count() == 0:
                    page.wait_for_timeout(500)
                print("ready selector found" if page.locator(b["ready"]).count() else "closing without ready selector")
                return 0
            _open_ready(page, b, shots)
            if a.cmd == "probe":
                try:
                    run_steps(page, b, {"chat": a.chat, "message": "(probe)"}, stop_before_final=True)
                    print("probe OK: all steps before the send action worked")
                    rc = 0
                except StepError as e:
                    print(f"probe FAILED at {e}")
                    rc = 1
                print("screenshot:", _screenshot(page, shots, "probe"))
                return rc
            ok, why = send_browser(page, b, shots, "manual", a.chat, a.text)
            print(("sent: " if ok else "FAILED: ") + why)
            return 0 if ok else 1
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
