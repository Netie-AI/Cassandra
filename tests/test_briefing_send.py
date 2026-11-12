"""Integration: `python -m src.briefing --edition morning --send` down to the Resend batch payload.

Nothing here touches the network or the real sqlite store. The edition is fixed (build_edition is
stubbed), httpx.post is captured, and everything in between (CLI, render, dispatch, store) is real.
"""
from __future__ import annotations

import datetime as dt
import re
import sqlite3

import pytest

import src.store as store
from src.briefing import __main__ as cli
from src.briefing import build, render, sources
from src.newsletter import send

BATCH_URL = "https://api.resend.com/emails/batch"
API_KEY = "re_test_key_123"
FROM = "Cassandra Briefing <briefing@test.example>"
SUBJECT = "Nvidia sells 250,000 chips to Singapore data centres"
HEADLINE = "Nvidia lands a record Singapore chip order"
STORY_URL = "https://news.example.com/nvidia-singapore-order"
ACTIVE = ["ann@example.com", "ben@example.com", "cho@example.com"]
GONE = "gone@example.com"
TOKEN_RE = re.compile(r"/api/digest/unsubscribe\?token=([A-Za-z0-9_\-]+)")


def _edition(**over) -> dict:
    q = sources.Quote("^GSPC", "S&P 500", "500 biggest US companies", 5000.0, 0.8, 1.2, "2026-11-12", False)
    story = sources.Story(id="s1", title="Nvidia sells 250,000 chips", summary="It paid $3 billion.",
                          url=STORY_URL, source="Reuters", region="sg",
                          published=dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc))
    ed = {
        "edition": "morning", "title": "Morning Edition", "date": "2026-11-13", "date_label": "Fri 13 Nov 2026",
        "subject": SUBJECT, "hook": "Chips are heading to Singapore.", "market_take": "Calm.",
        "big_picture": "AI spending keeps rising.", "talking_point": "Singapore is buying a lot of chips.",
        "markets": [build.market_block("Wall Street overnight", [q], today=dt.date(2026, 11, 13))],
        "stories": [{**story.to_dict(), "headline": HEADLINE, "what": "A big order.", "why": "More capacity.",
                     "edited": True}],
        "outlook": "Watch earnings.", "glossary": [{"term": "GPU", "plain": "A chip."}],
        "events": [], "calendar": [], "candidates": 12,
        "writer": "gemini", "rejected": [], "problems": [],
    }
    return {**ed, **over}


class _Resp:
    def __init__(self, n: int):
        self._n = n

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"data": [{"id": f"id-{i}"} for i in range(self._n)]}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Temp store, temp OUT_DIR, Resend configured, fixed edition, captured httpx.post."""
    monkeypatch.setattr(store, "DB", tmp_path / "test.sqlite")
    monkeypatch.setattr(cli, "OUT_DIR", tmp_path / "briefings")
    monkeypatch.setenv("_CASSANDRA_ENV_LOADED", "1")          # never read the repo's real .env
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("RESEND_FROM_DIGEST", FROM)
    monkeypatch.setenv("DIGEST_DOUBLE_OPTIN", "false")
    for name in ("SMTP_HOST", "RESEND_REPLY_TO", "NEWSLETTER_FROM"):
        monkeypatch.delenv(name, raising=False)

    state = {"edition": _edition(), "posts": [], "tmp": tmp_path}
    monkeypatch.setattr(build, "build_edition", lambda edition, **kw: state["edition"])

    def fake_post(url, *, headers=None, json=None, timeout=None, **kw):
        state["posts"].append({"url": url, "headers": headers, "json": json})
        return _Resp(len(json))

    monkeypatch.setattr(send.httpx, "post", fake_post)

    tokens = {}
    for email in ACTIVE + [GONE]:
        _, confirmed, token = store.save_digest_subscriber(email, "test")
        assert confirmed and token
        tokens[email] = token
    assert store.unsubscribe_digest(tokens[GONE]) == GONE
    state["tokens"] = tokens
    return state


def _emails(state) -> list[dict]:
    return [item for post in state["posts"] for item in post["json"]]


def _log(tmp_path) -> list[tuple[str, str]]:
    with sqlite3.connect(tmp_path / "test.sqlite") as c:
        return c.execute("SELECT email, message FROM contact_log ORDER BY id").fetchall()


def test_send_delivers_personalised_edition_to_confirmed_subscribers(env, capsys):
    assert cli.main(["--edition", "morning", "--send"]) == 0

    (post,) = env["posts"]
    assert post["url"] == BATCH_URL
    assert post["headers"]["Authorization"] == f"Bearer {API_KEY}"

    emails = post["json"]
    assert sorted(e["to"][0] for e in emails) == ACTIVE and all(len(e["to"]) == 1 for e in emails)
    tokens = env["tokens"]
    assert len(set(tokens.values())) == 4
    for e in emails:
        own = tokens[e["to"][0]]
        assert e["subject"] == SUBJECT and e["from"] == FROM
        for body in (e["html"], e["text"]):
            assert TOKEN_RE.findall(body) == [own]                       # exactly one unsub link, their own
            assert not any(t in body for addr, t in tokens.items() if t != own)
            assert render.UNSUB_PLACEHOLDER not in body and "__UNSUB_" not in body
            assert STORY_URL in body and HEADLINE in body
        assert f"href='{STORY_URL}'" in e["html"]

    # audit trail + last_sent_at only for those who were sent to
    log = _log(env["tmp"])
    assert sorted(a for a, _ in log) == ACTIVE and all("ok=True" in m for _, m in log)
    with sqlite3.connect(env["tmp"] / "test.sqlite") as c:
        sent_rows = dict(c.execute("SELECT email, last_sent_at FROM digest_subscribers").fetchall())
    assert all(sent_rows[a] for a in ACTIVE) and sent_rows[GONE] is None

    # the saved copy went to tmp_path and still carries the placeholder, never a real token
    saved = (env["tmp"] / "briefings" / "2026-11-13-morning.html").read_text(encoding="utf-8")
    assert HEADLINE in saved and not any(t in saved for t in tokens.values())
    assert "'sent': 3" in capsys.readouterr().out


def test_wire_edition_is_not_sent_unless_allowed(env, capsys):
    env["edition"] = _edition(writer="wire")
    assert cli.main(["--edition", "morning", "--send"]) == 1
    assert env["posts"] == [] and _log(env["tmp"]) == []
    assert "--allow-wire" in capsys.readouterr().err

    assert cli.main(["--edition", "morning", "--send", "--allow-wire"]) == 0
    assert sorted(e["to"][0] for e in _emails(env)) == ACTIVE


def test_empty_edition_is_not_sent(env):
    env["edition"] = _edition(stories=[], markets=[])
    assert cli.main(["--edition", "morning", "--send"]) == 1
    assert env["posts"] == []


def test_dry_run_sends_nothing_and_lists_recipients(env, capsys):
    assert cli.main(["--edition", "morning", "--dry-run"]) == 0
    assert env["posts"] == [] and _log(env["tmp"]) == []
    out = capsys.readouterr().out
    assert all(a in out for a in ACTIVE) and GONE not in out


def test_no_flags_builds_and_saves_but_sends_nothing(env):
    assert cli.main(["--edition", "morning"]) == 0
    assert env["posts"] == []
    assert (env["tmp"] / "briefings" / "latest.html").exists()


def test_resend_failure_returns_nonzero_and_logs_each_failure(env, monkeypatch, capsys):
    def boom(*a, **kw):
        raise send.httpx.ConnectError("resend is down")

    monkeypatch.setattr(send.httpx, "post", boom)
    assert cli.main(["--edition", "morning", "--send"]) == 1
    assert "'failed': 3" in capsys.readouterr().out

    log = _log(env["tmp"])
    assert sorted(a for a, _ in log) == ACTIVE
    assert all("ok=False" in m and "resend is down" in m for _, m in log)
    with sqlite3.connect(env["tmp"] / "test.sqlite") as c:
        assert c.execute("SELECT COUNT(*) FROM digest_subscribers WHERE last_sent_at IS NOT NULL").fetchone()[0] == 0


def test_http_error_status_also_counts_as_failure(env, monkeypatch):
    class Bad(_Resp):
        def raise_for_status(self):
            raise send.httpx.HTTPError("422 Unprocessable Entity")

    monkeypatch.setattr(send.httpx, "post", lambda *a, **kw: Bad(0))
    assert cli.main(["--edition", "morning", "--send"]) == 1
    assert all("ok=False" in m for _, m in _log(env["tmp"]))


def test_more_than_100_subscribers_are_split_into_two_batches(env):
    for i in range(98):                                                   # 3 active + 98 = 101
        store.save_digest_subscriber(f"reader{i:03d}@example.com", "test")
    recipients = store.list_digest_recipients()
    assert len(recipients) == 101

    assert cli.main(["--edition", "morning", "--send"]) == 0
    assert [p["url"] for p in env["posts"]] == [BATCH_URL, BATCH_URL]
    assert [len(p["json"]) for p in env["posts"]] == [100, 1]
    emails = _emails(env)
    assert sorted(e["to"][0] for e in emails) == sorted(r["email"] for r in recipients)
    by_email = {r["email"]: r["unsub_token"] for r in recipients}
    assert all(TOKEN_RE.findall(e["html"]) == [by_email[e["to"][0]]] for e in emails)


def test_unsubscribe_link_from_a_sent_email_removes_reader_from_next_send(env):
    assert cli.main(["--edition", "morning", "--send"]) == 0
    target = next(e for e in _emails(env) if e["to"] == ["ben@example.com"])
    (token,) = TOKEN_RE.findall(target["html"])

    assert store.unsubscribe_digest(token) == "ben@example.com"
    assert store.unsubscribe_digest(token) is None                        # the link is single use

    env["posts"].clear()
    env["edition"]["subject"] = "The next edition"                         # same subject would be a re-run
    assert cli.main(["--edition", "morning", "--send"]) == 0
    assert sorted(e["to"][0] for e in _emails(env)) == ["ann@example.com", "cho@example.com"]


def test_rerun_of_the_same_edition_does_not_double_send(env):
    """A crash or partial failure followed by a re-run must only reach readers not yet served."""
    assert cli.main(["--edition", "morning", "--send"]) == 0
    assert len(_emails(env)) == 3
    env["posts"].clear()
    store.save_digest_subscriber("new@example.com", "test")
    assert cli.main(["--edition", "morning", "--send"]) == 0
    assert [e["to"][0] for e in _emails(env)] == ["new@example.com"]


def test_batch_emails_carry_edition_tags(env):
    assert cli.main(["--edition", "morning", "--send"]) == 0
    assert {"name": "type", "value": "briefing_morning"} in _emails(env)[0]["tags"]
