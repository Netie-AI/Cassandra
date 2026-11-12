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


def test_clean_keeps_text_between_bare_angle_brackets():
    """Regression: 'cost < $5 ... revenue > $9 billion' used to collapse to 'cost $9 billion'."""
    assert sources._clean("AI cost &lt; $5 a month, revenue &gt; $9 billion &lt;b&gt;now&lt;/b&gt;") == \
        "AI cost < $5 a month, revenue > $9 billion now"


def test_dates_without_a_timezone_are_dropped_and_sgt_is_understood():
    assert sources._parse_date("Thu, 12 Nov 2026 08:00:00 SGT") == dt.datetime(2026, 11, 12, 0, 0, tzinfo=UTC)
    assert sources._parse_date("2026-11-12T08:00:00") is None
    assert sources._parse_date("2026-11-12") is None


def test_ai_keyword_filter_matches_whole_words():
    kw = sources.load_config()["ai_keywords"]
    hit = lambda t: sources._is_ai(_story(title=t, summary=""), kw)
    assert all(hit(t) for t in ("AI: the new boom", "Is this the end for 'AI'?", "Nvidia chips sell out"))
    assert not any(hit(t) for t in ("Chipotle raises burrito prices", "Dubai-based firm lists in Singapore",
                                    "Samurai-themed cafe opens", "Microchipping pets becomes mandatory"))


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


def test_quote_rejects_bad_closes_and_multi_session_gaps():
    day0 = 1793926800
    nan_last = _chart([100.0, 110.0, float("nan")], None, 0)
    assert sources.parse_chart(nan_last, symbol="X", label="X", note="").close == 110.0     # NaN bar ignored
    gap = {"chart": {"result": [{"meta": {"gmtoffset": 0}, "timestamp": [day0, day0 + 9 * 86400],
                                 "indicators": {"quote": [{"close": [100.0, 105.0]}]}}]}}
    assert sources.parse_chart(gap, symbol="X", label="X", note="").pct_1d is None            # not a 1-day move


def test_quote_needs_two_sessions():
    with pytest.raises(ValueError):
        sources.parse_chart(_chart([None, None], 5.0, 1793926800), symbol="X", label="X", note="")


# ── fact check ───────────────────────────────────────────────────────────────
def test_ungrounded_numbers_pair_value_with_unit():
    src = "Mastercard to add over 250 jobs by end-2029, worth $3.5 billion"
    assert writer.ungrounded("Mastercard adds 250 jobs by 2029 for $3.5bn", src) == set()
    assert writer.ungrounded("Mastercard adds 300 jobs", src) == {(300.0, "")}
    assert writer.ungrounded("two hundred and fifty jobs", src) == {"two", "hundred", "fifty"}
    assert writer.ungrounded("1,000 chips", "it made 1000 chips") == set()
    assert writer.ungrounded("$35.1 billion", "revenue of $35.1bn") == set()


@pytest.mark.parametrize("source, copy", [
    ("Startup raises $3 million as AI market tops $1 billion", "Startup raises $3 billion"),   # unit swap
    ("Anthropic raises $3bn", "Anthropic raises $3tn"),
    ("OpenAI launches GPT-5 for 200 firms", "OpenAI cut 5 percent of staff"),                  # 5 is not 5%
    ("Shares up 5 points", "Shares up 5 percent"),
    ("Google buys two startups", "Google buys nine startups"),                                 # small number words
    ("Nvidia shares fell 8% after earnings", "Nvidia shares soar 8% after earnings"),          # direction flip
    ("Apple denies plan to buy Perplexity", "Apple to buy Perplexity"),                        # dropped denial
    ("Apple buys Perplexity", 'Apple boss says "this is a done deal"'),                        # invented quote
])
def test_adversarial_copy_is_rejected(source, copy):
    assert writer.check_story_text(copy, source), f"accepted: {copy!r}"


@pytest.mark.parametrize("source, copy", [
    ("Nvidia shares fell 8% after earnings", "Nvidia shares dropped 8% after its results"),
    ("Apple denies plan to buy Perplexity", "Apple denies it plans to buy Perplexity"),
    ("OpenAI launches GPT-5 for 200 firms", "OpenAI launches GPT-5 for 200 companies"),
])
def test_faithful_copy_is_accepted(source, copy):
    assert writer.check_story_text(copy, source) == []


def test_market_commentary_must_match_data_and_give_no_advice():
    assert writer.check_free_text("Markets were calm and investors waited.", {"up"}) == []
    assert writer.check_free_text("Stocks slipped as investors worried.", {"up"})        # nothing fell
    assert writer.check_free_text("Stocks rallied.", {"down"})
    assert writer.check_free_text("Stocks fell by a third.", {"down"}) == []             # allowed: no digits
    assert writer.check_free_text("Chip shares lost half their value.", {"down"})        # quantity word
    assert writer.check_free_text("Buy Nvidia now.", {"up", "down"})
    assert writer.check_free_text("Stocks rose 2% today.", {"up"})


def test_ground_keeps_good_copy_and_rejects_invented_facts():
    stories = [_story(1), _story(2, title="Google launches glasses", summary="")]
    raw = {
        "subject": "Nvidia sells 250 chips and much more besides, a very long subject line that runs on",
        "hook": "A big day: 900 things happened.",                   # 900 is nowhere in the sources
        "market_take": "Stocks slipped today.",                      # data shows only risers
        "outlook": "Watch chip makers closely.",
        "big_picture": "AI spending keeps growing.",
        "talking_point": "Nvidia paid $3 billion.",
        "stories": [
            {"id": "s1", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.", "why": "This matters."},
            {"id": "s2", "headline": "Google glasses cost $99", "what": "Google launched glasses.", "why": "Try it."},
            {"id": "s9", "headline": "Invented", "what": "x", "why": "y"},      # id not in candidates
            {"id": "s1", "headline": "Duplicate", "what": "x", "why": "y"},     # same story twice
        ],
    }
    out = writer.ground(raw, stories, {"up"})
    assert [s["id"] for s in out["stories"]] == ["s1", "s2"]
    assert out["stories"][0]["edited"] is True
    assert out["stories"][1]["headline"] == "Google launches glasses"         # fell back to the source title
    assert out["stories"][1]["edited"] is False
    assert out["hook"] == "" and out["market_take"] == ""
    assert out["outlook"] == "Watch chip makers closely."
    assert out["big_picture"] and out["talking_point"] == "Nvidia paid $3 billion."
    assert len(out["subject"]) <= writer.SUBJECT_MAX and not out["subject"].endswith(" ")
    assert len(out["rejected"]) == 5


def test_no_key_falls_back_to_labelled_wire_copy(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    stories = [_story(i) for i in range(1, 6)] + [_story(7, title="Is AI over?"), _story(8, summary="I think so.")]
    out = writer.write_copy(stories, edition="morning", date_label="x",
                            market_facts=[], market_dirs=set(), events=[])
    assert out["writer"] == "wire" and "GEMINI_API_KEY" in out["writer_note"]
    assert len(out["stories"]) == 2                                            # max 2 per source, no opinion


def test_model_failure_note_never_leaks_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-KEY-123")
    monkeypatch.setattr(writer, "RETRY_PAUSE_S", 0)

    def boom(*a, **k):
        raise RuntimeError("503 for url https://x/generateContent?key=SECRET-KEY-123")

    monkeypatch.setattr(writer, "_gemini_generate", boom)
    out = writer.write_copy([_story()], edition="morning", date_label="x",
                            market_facts=[], market_dirs=set(), events=[])
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


def test_calendar_parsing_explains_and_filters():
    cal = sources.load_config()["calendar"]
    sgt = dt.timezone(dt.timedelta(hours=8))
    now = dt.datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    ff = [
        {"title": "CPI m/m", "country": "USD", "date": "2026-11-12T08:30:00-05:00", "impact": "High"},
        {"title": "Core CPI m/m", "country": "USD", "date": "2026-11-12T08:30:00-05:00", "impact": "High"},   # same event
        {"title": "CPI m/m", "country": "EUR", "date": "2026-11-12T08:30:00-05:00", "impact": "High"},        # not US
        {"title": "Natural Gas Storage", "country": "USD", "date": "2026-11-12T10:30:00-05:00", "impact": "Medium"},
        {"title": "Unemployment Claims", "country": "USD", "date": "2026-11-20T08:30:00-05:00", "impact": "High"},  # too far
        {"title": "PPI m/m", "country": "USD", "date": "2026-11-12T08:30:00", "impact": "High"},              # no timezone
    ]
    (row,) = sources.parse_econ(ff, start=now, end=now + dt.timedelta(hours=30), tz=sgt, explain=cal["explain"])
    assert row["when"] == "Thu 12 Nov, 21:30 Singapore time" and "inflation" in row["plain"]

    nasdaq = {"data": {"rows": [{"symbol": "NVDA", "time": "time-after-hours"}, {"symbol": "ZZZZ", "time": "x"}]}}
    (e,) = sources.parse_earnings(nasdaq, day=dt.date(2026, 11, 17), watchlist=cal["watchlist"])
    assert e["title"] == "Nvidia reports quarterly results" and "early next morning in Singapore" in e["when"]
    assert sources.parse_earnings({"data": {"rows": None}}, day=dt.date(2026, 11, 14), watchlist={}) == []


def test_glossary_hits_are_curated_terms_only():
    hits = sources.glossary_hits("New data centre uses 5,000 GPUs, capex soars")
    assert [h["term"] for h in hits] == ["Data centre", "GPU / AI chip", "Capex"]
    assert sources.glossary_hits("nothing technical here") == []


# ── render ───────────────────────────────────────────────────────────────────
def _edition(**over):
    q = sources.Quote("^GSPC", "S&P 500", "500 biggest US companies", 5000.0, -0.04, 1.2, "2026-11-12", False)
    ed = {
        "edition": "morning", "title": "Morning Edition", "date": "2026-11-13", "date_label": "Fri 13 Nov 2026",
        "subject": "s", "hook": "Hook <script>", "market_take": "Calm.", "big_picture": "BP",
        "talking_point": "TP",
        "markets": [build.market_block("Wall Street overnight", [q], today=dt.date(2026, 11, 13))],
        "stories": [{**_story().to_dict(), "headline": "H <b>x</b>", "what": "W", "why": "Y", "edited": True,
                     "url": "https://ex.com/?a=1&b='2'"}],
        "outlook": "Watch.", "glossary": [{"term": "GPU", "plain": "A chip."}],
        "events": sources.upcoming_events(dt.date(2027, 5, 30)),
        "calendar": [{"title": "CPI m/m", "when": "Thu 12 Nov, 21:30 Singapore time", "plain": "the US inflation report"}],
        "writer": "gemini", "rejected": [], "problems": ["price for Nikkei unavailable (Timeout)"],
    }
    return {**ed, **over}


def test_render_html_escapes_untrusted_text_and_shows_everything():
    html = render.render_html(_edition())
    assert "<script>" not in html and "<b>x</b>" not in html
    assert "href='https://ex.com/?a=1&amp;b=&#x27;2&#x27;'" in html           # quote cannot break the attribute
    assert "0.0%" not in html and ">flat<" in html                             # no "-0.0%"
    assert "Say this at lunch" in html and "What it means for you" in html
    assert "Jargon buster" in html and "In plain English: the US inflation report." in html
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


def _q(label, pct, date="2026-11-12"):
    return sources.Quote(label, label, "", 100.0, pct, pct, date, False)


def test_market_summary_names_the_big_mover_and_matches_the_printed_number():
    block = build.market_block("US", [_q("S&P 500", 0.1), _q("Nasdaq", -2.4), _q("Nvidia", -9.8)])
    assert block["summary"] == "S&P 500 was flat (+0.1%). Biggest move: Nvidia fell sharply (-9.8%)."
    assert build.market_dirs([block]) == {"down"}                              # +0.1% does not count as "rose"
    for pct in (0.149, 0.15, 1.46, 1.5, -0.04):                                # same printed number, same word
        b = build.market_block("US", [_q("X", pct)])
        word = "sharply" if abs(round(pct, 1)) >= 1.5 else ""
        assert ("sharply" in b["summary"]) == bool(word)
        assert ("flat" in b["summary"]) == (abs(round(pct, 1)) < 0.2)


def test_market_block_marks_rows_from_an_older_session():
    block = build.market_block("Asia", [_q("STI", 1.2, "2026-11-11"), _q("Nikkei", -0.5, "2026-11-12")])
    assert block["rows"][0]["old"] and not block["rows"][1]["old"]
    assert block["summary"].startswith("STI did not trade in the latest session.")
    html = render.render_html(_edition(markets=[block]))
    assert "last traded Wed 11 Nov" in html


def test_unsub_placeholder_cannot_be_forged_by_feed_text():
    """Regression: a fixed placeholder inside a story URL would receive each reader's token."""
    assert render.UNSUB_PLACEHOLDER != "__UNSUB_TOKEN__" and len(render.UNSUB_PLACEHOLDER) > 30
    ed = _edition()
    ed["stories"][0]["url"] = "https://evil.example/c?t=__UNSUB_TOKEN__"
    sent = render.render_html(ed).replace(render.UNSUB_PLACEHOLDER, "SECRET-TOKEN")
    assert sent.count("SECRET-TOKEN") == 1 and "evil.example/c?t=SECRET" not in sent


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
