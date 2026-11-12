"""AI Briefing: offline tests for parsing, fact-check grounding, scheduling and rendering."""
from __future__ import annotations

import datetime as dt

import pytest

from src.briefing import build, render, sources, writer

UTC = dt.timezone.utc

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>OpenAI ships &lt;b&gt;new&lt;/b&gt; model - Reuters</title><link>https://ex.com/a</link>
  <description>&lt;p&gt;It costs $20 a month.&lt;/p&gt;</description>
  <pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
<item><title>Singapore unveils AI plan</title><link>https://ex.com/b</link>
  <pubDate>Thu, 12 Nov 2026 09:00:00 +0800</pubDate></item>
<item><title>No date, must be dropped</title><link>https://ex.com/c</link></item>
<item><title>Bad link</title><link>javascript:alert(1)</link><pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom story</title>
<link rel="alternate" href="https://ex.com/atom"/><summary>hello</summary>
<published>2026-11-12T10:00:00Z</published></entry></feed>"""


def _story(i=1, title="Nvidia sells 250 chips", summary="It paid $3 billion.", region="global"):
    return sources.Story(id=f"s{i}", title=title, summary=summary, url=f"https://ex.com/{i}",
                         source="Src", region=region, published=dt.datetime(2026, 11, 12, tzinfo=UTC))


# ── feeds ────────────────────────────────────────────────────────────────────
def test_parse_rss_cleans_dates_and_drops_unverifiable_items():
    items = sources.parse_feed(RSS, source="Google News")
    assert [s.url for s in items] == ["https://ex.com/a", "https://ex.com/b"]
    a, b = items
    assert a.title == "OpenAI ships new model" and a.source == "Reuters"     # tags + publisher suffix gone
    assert a.summary == "It costs $20 a month."
    assert a.region == "global" and b.region == "sg"                          # tagged by content
    assert b.published == dt.datetime(2026, 11, 12, 1, 0, tzinfo=UTC)         # +0800 normalised to UTC


def test_parse_atom():
    (s,) = sources.parse_feed(ATOM, source="Verge")
    assert (s.title, s.url, s.summary) == ("Atom story", "https://ex.com/atom", "hello")


# ── prices ───────────────────────────────────────────────────────────────────
def _chart(closes, market_price, market_time, day0=1793926800):
    return {"chart": {"result": [{
        "meta": {"gmtoffset": 28800, "regularMarketPrice": market_price, "regularMarketTime": market_time},
        "timestamp": [day0 + 86400 * i for i in range(len(closes))],
        "indicators": {"quote": [{"close": closes}]},
    }]}}


def test_quote_uses_meta_price_when_latest_bar_is_empty():
    """Regression: Yahoo leaves the newest bar null after the close. The old code silently
    reported the previous session (wrong day, wrong % change)."""
    day0 = 1793926800                                   # 2026-11-06 09:00 SGT
    payload = _chart([100.0, 110.0, None], 99.0, day0 + 2 * 86400 + 8 * 3600)
    q = sources.parse_chart(payload, symbol="^STI", label="STI", note="")
    assert q.session_date == "2026-11-08"
    assert q.close == 99.0
    assert q.pct_1d == pytest.approx(-10.0)


def test_quote_needs_two_sessions():
    with pytest.raises(ValueError):
        sources.parse_chart(_chart([None, None], 5.0, 1793926800), symbol="X", label="X", note="")


# ── fact check ───────────────────────────────────────────────────────────────
def test_ungrounded_numbers():
    src = "Mastercard to add over 250 jobs by end-2029, worth $3.5 billion"
    assert writer.ungrounded("Mastercard adds 250 jobs by 2029 for $3.5 billion", src) == set()
    assert writer.ungrounded("Mastercard adds 300 jobs", src) == {"300"}
    assert writer.ungrounded("two hundred and fifty jobs", src) == {"hundred", "fifty"}   # spelled out
    assert writer.ungrounded("1,000 chips", "it made 1000 chips") == set()


def test_ground_keeps_good_copy_and_rejects_invented_facts():
    stories = [_story(1), _story(2, title="Google launches glasses", summary="")]
    raw = {
        "subject": "Nvidia sells 250 chips",
        "hook": "A big day: 900 things happened.",                   # 900 is nowhere in the sources
        "market_take": "Stocks rose 2% today.",                      # digits banned here
        "outlook": "Watch chip makers closely.",
        "stories": [
            {"id": "s1", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.", "why": "This matters."},
            {"id": "s2", "headline": "Google glasses cost $99", "what": "Google launched glasses.", "why": "Try it."},
            {"id": "s9", "headline": "Invented", "what": "x", "why": "y"},      # id not in candidates
            {"id": "s1", "headline": "Duplicate", "what": "x", "why": "y"},     # same story twice
        ],
    }
    out = writer.ground(raw, stories, "S&P 500 +0.4%")
    assert [s["id"] for s in out["stories"]] == ["s1", "s2"]
    assert out["stories"][0]["edited"] is True
    assert out["stories"][1]["headline"] == "Google launches glasses"         # fell back to the source title
    assert out["stories"][1]["edited"] is False
    assert out["hook"] == "" and out["market_take"] == ""
    assert out["outlook"] == "Watch chip makers closely."
    assert len(out["rejected"]) == 5


def test_no_key_falls_back_to_labelled_wire_copy(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    out = writer.write_copy([_story(i) for i in range(1, 6)], edition="morning", date_label="x",
                            market_facts=[], events=[])
    assert out["writer"] == "wire" and "GEMINI_API_KEY" in out["writer_note"]
    assert len(out["stories"]) == 2                                            # max 2 per source


def test_model_failure_note_never_leaks_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-KEY-123")
    monkeypatch.setattr(writer, "RETRY_PAUSE_S", 0)

    def boom(*a, **k):
        raise RuntimeError("503 for url https://x/generateContent?key=SECRET-KEY-123")

    monkeypatch.setattr(writer, "_gemini_generate", boom)
    out = writer.write_copy([_story()], edition="morning", date_label="x", market_facts=[], events=[])
    assert out["writer"] == "wire"
    assert "SECRET" not in out["writer_note"] and "RuntimeError" in out["writer_note"]


# ── schedule + events ────────────────────────────────────────────────────────
def test_pick_edition():
    sched = sources.load_config()["schedule"]
    at = lambda d, h, m: dt.datetime(2026, 11, d, h, m)          # 9 Nov 2026 is a Monday
    assert build.pick_edition(at(10, 7, 35), sched) == "morning"     # Tue
    assert build.pick_edition(at(9, 7, 35), sched) is None           # Mon morning: US was shut on Sunday
    assert build.pick_edition(at(9, 20, 40), sched) == "evening"
    assert build.pick_edition(at(14, 20, 40), sched) is None         # Sat evening
    assert build.pick_edition(at(15, 9, 0), sched) == "weekly"       # Sun
    assert build.pick_edition(at(10, 7, 29), sched) is None          # before the slot
    assert build.pick_edition(at(10, 12, 0), sched) is None          # too late


def test_events_file_is_valid_and_countdown_works():
    events = sources.load_config("events")["events"]
    for ev in events:
        assert isinstance(ev["start"], dt.date) and ev["source"].startswith("https://") and ev["why"]
        assert ev.get("end", ev["start"]) >= ev["start"]
    rows = sources.upcoming_events(dt.date(2026, 11, 16), horizon_days=14, events=events)
    assert rows[0]["name"].startswith("Nvidia") and rows[0]["days_away"] == 1
    during = sources.upcoming_events(dt.date(2026, 11, 19), horizon_days=14, events=events)
    assert during[0]["ongoing"] and "FinTech" in during[0]["name"]            # Nvidia (17th) has passed
    far = sources.upcoming_events(dt.date(2027, 4, 1), horizon_days=14, events=events)
    assert len(far) == 1                                                       # nothing near: show the next one


def test_glossary_hits_are_curated_terms_only():
    hits = sources.glossary_hits("New data centre uses 5,000 GPUs, capex soars")
    assert [h["term"] for h in hits] == ["Data centre", "GPU / AI chip", "Capex"]
    assert sources.glossary_hits("nothing technical here") == []


# ── render ───────────────────────────────────────────────────────────────────
def _edition(**over):
    q = sources.Quote("^GSPC", "S&P 500", "500 biggest US companies", 5000.0, -0.04, 1.2, "2026-11-12", False)
    ed = {
        "edition": "morning", "title": "Morning Edition", "date": "2026-11-13", "date_label": "Fri 13 Nov 2026",
        "subject": "s", "hook": "Hook <script>", "market_take": "Calm.",
        "markets": [build.market_block("Wall Street overnight", [q], today=dt.date(2026, 11, 13))],
        "stories": [{**_story().to_dict(), "headline": "H <b>x</b>", "what": "W", "why": "Y", "edited": True,
                     "url": "https://ex.com/?a=1&b='2'"}],
        "outlook": "Watch.", "glossary": [{"term": "GPU", "plain": "A chip."}],
        "events": sources.upcoming_events(dt.date(2027, 5, 30)),
        "writer": "gemini", "rejected": [], "problems": ["price for Nikkei unavailable (Timeout)"],
    }
    return {**ed, **over}


def test_render_html_escapes_untrusted_text_and_shows_everything():
    html = render.render_html(_edition())
    assert "<script>" not in html and "<b>x</b>" not in html
    assert "href='https://ex.com/?a=1&amp;b=&#x27;2&#x27;'" in html           # quote cannot break the attribute
    assert "-0.0%" not in html and "+0.0%" in html                             # no negative zero
    assert "Why it matters" in html and "Jargon buster" in html
    assert "date not yet confirmed" in html                                    # Computex 2027 flag
    assert "price for Nikkei unavailable" in html                              # degradation is visible
    assert render.UNSUB_PLACEHOLDER in html
    assert "—" not in html


def test_render_text_has_links_and_unsub():
    text = render.render_text(_edition())
    assert "https://ex.com/?a=1&b='2'" in text and render.UNSUB_PLACEHOLDER in text


def test_market_block_flags_closed_markets():
    q = sources.Quote("^GSPC", "S&P 500", "", 5000.0, 0.5, 1.0, "2026-11-06", False)
    block = build.market_block("Wall Street", [q], today=dt.date(2026, 11, 12))
    assert block["stale"] and "rose" in block["summary"]
    assert build.market_block("x", []) is None


def test_dispatch_rendered_swaps_unsub_token(monkeypatch):
    from src.newsletter import send

    sent = []
    monkeypatch.setattr("src.store.list_digest_recipients",
                        lambda: [{"email": "a@x.com", "unsub_token": "tok-a"}])
    monkeypatch.setattr(send, "is_configured", lambda: True)
    monkeypatch.setattr(send, "_dispatch", lambda recs, subj, render_fn, tags: sent.append(render_fn(recs[0])) or {})
    send.dispatch_rendered(subject="s", html="<a href='?token=__T__'>", text="u __T__",
                           unsub_placeholder="__T__", tags={})
    assert sent == [("<a href='?token=tok-a'>", "u tok-a")]
    dry = send.dispatch_rendered(subject="s", html="", text="", unsub_placeholder="__T__", tags={}, dry_run=True)
    assert dry["dry_run"] and dry["recipients"] == ["a@x.com"] and len(sent) == 1
