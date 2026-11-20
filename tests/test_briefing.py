"""AI Briefing: offline tests for parsing, fact-check grounding, scheduling and rendering."""
from __future__ import annotations

import datetime as dt
import json

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


def test_one_day_change_never_spans_a_missing_session():
    """Live 2026-11-20: Taiwan's previous bar was empty, so the edition printed -8.5% for a -3.1% day."""
    day0 = 1793926800
    payload = _chart([100.0, 110.0, None, 99.0], 99.0, day0 + 3 * 86400 + 3600)        # day 2 has no close
    assert sources.parse_chart(payload, symbol="X", label="X", note="").pct_1d is None
    payload["chart"]["result"][0]["meta"]["regularMarketChangePercent"] = -3.114        # Yahoo's own figure wins
    assert sources.parse_chart(payload, symbol="X", label="X", note="").pct_1d == pytest.approx(-3.114)
    ok = _chart([100.0, 110.0], 110.0, day0 + 86400 + 3600)
    ok["chart"]["result"][0]["meta"]["regularMarketChangePercent"] = 0.0               # pre-open placeholder
    assert sources.parse_chart(ok, symbol="X", label="X", note="").pct_1d == pytest.approx(10.0)


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
    assert writer.check_story_text(copy, source, title=source), f"accepted: {copy!r}"


@pytest.mark.parametrize("source, copy", [
    ("Nvidia shares fell 8% after earnings", "Nvidia shares dropped 8% after its results"),
    ("Apple denies plan to buy Perplexity", "Apple denies it plans to buy Perplexity"),
    ("OpenAI launches GPT-5 for 200 firms", "OpenAI launches GPT-5 for 200 companies"),
])
def test_faithful_copy_is_accepted(source, copy):
    assert writer.check_story_text(copy, source, title=source) == []


@pytest.mark.parametrize("source, copy", [
    ("Shares fell 8% on Monday", "Shares up 8% on Monday"),                     # "up" + figure is a direction
    ("Shares rose 8%", "Shares lost 8%"),
    ("Shares rose 8%", "Shares down 8%"),
    ("Apple may buy Perplexity", "Apple buys Perplexity"),                      # talks are not done deals
    ("Apple in talks to buy Perplexity", "Apple buys Perplexity"),
    ("Apple won't buy Perplexity", "Apple buys Perplexity"),
    ("Firm raises US$3 billion", "Firm raises S$3 billion"),                    # currency swap
    ("Firm raises 3 billion yen", "Firm raises $3 billion"),
])
def test_second_round_adversarial_copy_is_rejected(source, copy):
    assert writer.check_story_text(copy, source, title=source), f"accepted: {copy!r}"


@pytest.mark.parametrize("source, copy", [
    ("Sales up 20% this year", "Sales rose 20% this year"),                      # used to be falsely rejected
    ("Shares down 20%", "Shares fell 20%"),
    ("Firm raises US$3 billion", "Firm raises $3 billion"),
    ("Apple may buy Perplexity", "Apple could buy Perplexity"),
    ("Users sign up for the new startup tool", "People sign up for a new tool"),  # "up" without a figure
])
def test_second_round_faithful_copy_is_accepted(source, copy):
    assert writer.check_story_text(copy, source, title=source) == []


def test_hedge_in_summary_does_not_reject_a_faithful_rewrite():
    """Regression: a stray 'could'/'not' in the summary rejected most rewrites in a live run."""
    src = _story(1, title="United Airlines blocks AI agents from booking flights",
                 summary="The airline said it could not verify automated tools and will not allow them.")
    raw = {"hook": "An airline blocks AI tools.", "subject": "United blocks AI agents",
           "stories": [{"id": "s1", "headline": "United Airlines blocks AI booking tools",
                        "what": "United Airlines is stopping automated AI tools from booking flights.", "why": ""}]}
    out = writer.ground(raw, [src], set())
    assert out["stories"][0]["edited"] is True and out["rejected"] == []


def test_opening_lines_are_rebuilt_when_a_picked_story_is_dropped():
    rude = _story(1, title="Founder's pathetic pivot mocked", summary="")
    ok = _story(2, title="Google launches glasses", summary="")
    raw = {"subject": "Founder pivots, Google launches glasses", "hook": "A founder pivots today.",
           "stories": [{"id": "s1", "headline": "Founder's pathetic pivot", "what": "", "why": ""},
                       {"id": "s2", "headline": "Google launches glasses", "what": "", "why": ""}]}
    out = writer.ground(raw, [rude, ok], set())
    assert out["hook"] == "" and out["subject"] == "Google launches glasses"


def test_subject_cannot_glue_one_storys_number_to_another_storys_company():
    corpora = ["OpenAI raises $40 billion", "Singapore startup hires 12 people"]
    assert writer.check_spanning("OpenAI raises $40 billion, Singapore startup hires 12", corpora) == []
    assert writer.check_spanning("Singapore startup raises $40 billion and hires 12", corpora)
    assert writer.check_spanning("A busy day in AI", corpora) == []


def test_why_line_cannot_state_new_facts_or_advice():
    src = _story(1, title="Nvidia reports results", summary="Revenue was $35 billion.")
    raw = {"stories": [{"id": "s1", "headline": "Nvidia reports results", "what": "Revenue was $35 billion.",
                        "why": "If you own the shares, they soared and you should definitely buy more."}]}
    out = writer.ground(raw, [src], set())
    assert out["stories"][0]["why"] == "" and out["stories"][0]["edited"] is True


def test_respect_filter_does_not_block_ordinary_news_words():
    for ok in ("Singapore's Ministry of Home Affairs to use AI to spot scams", "OpenAI hires head of global affairs",
               "UK to ban AI apps that create nude images", "Winners and losers of the AI chip boom",
               "Figma adds AI mockups", "Nvidia's fat margins", "Musk slams OpenAI in court filing"):
        assert not writer.disrespectful(ok), ok
    for bad in ("CEO resigns amid spy, affair scandals", "Nvidia CEO resigns over affairs", "the alleged spy affair broke", "He quit over an affair with a colleague",
                "reports of two extramarital affairs", "Founder's pathetic attempt to pivot"):
        assert writer.disrespectful(bad), bad


def test_market_commentary_must_match_data_and_give_no_advice():
    assert writer.check_free_text("Stocks rose because of the OpenAI deal.", {"up"})       # cause claim
    assert writer.check_free_text("Nvidia will fall after its results, steer clear.")       # certainty + advice
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
    assert out["big_picture"] == "AI spending keeps growing."
    assert len(out["subject"]) <= writer.SUBJECT_MAX and not out["subject"].endswith(" ")
    assert len(out["rejected"]) == 6                                          # incl. title-only "what"


def test_gossip_and_insults_never_run():
    """Owner rule: nothing that reads like bullying or gossip about a person."""
    src = _story(1, title="Nvidia CEO resigns amid affair scandal", summary="The board accepted his resignation.")
    rude = _story(2, title="Founder's pathetic pivot mocked online", summary="")
    ok = _story(3, title="Google launches glasses", summary="")
    raw = {"big_picture": "The boss had an affair, people say.", "hook": "A chief executive quit.",
           "stories": [
               {"id": "s1", "headline": "Nvidia chief executive resigns after a scandal",
                "what": "He quit after an extramarital affair.", "why": "For investors, leadership may change."},
               {"id": "s2", "headline": "Founder's pathetic pivot", "what": "", "why": ""},
               {"id": "s3", "headline": "Google launches glasses", "what": "Google launched glasses.", "why": ""}]}
    out = writer.ground(raw, [src, rude, ok], set())
    assert [s["id"] for s in out["stories"]] == ["s1", "s3"]             # s2: no respectful wording available
    top = out["stories"][0]
    assert top["headline"] == "Nvidia chief executive resigns after a scandal"
    assert top["what"] == "The board accepted his resignation."          # gossip line replaced by the source summary
    assert out["big_picture"] == "" and out["hook"] == ""               # hook rebuilt: s2 was dropped
    assert not writer.disrespectful("Nvidia's chief executive resigned after a scandal, and the board named a successor.")
    wire = writer.wire_copy([src, rude, ok], "x")
    assert [s["id"] for s in wire["stories"]] == ["s3"]


def test_title_only_source_gets_no_invented_summary():
    """Live run 2026-11-13: a title-only story got a 'what' describing details the title never gave."""
    src = _story(1, title="Scale AI Launches Singapore Legal Reasoning Benchmark with IMDA", summary="")
    raw = {"stories": [{"id": "s1", "headline": "Scale AI launches Singapore legal benchmark with IMDA",
                        "what": "The system tests how accurately models process local legal facts.",
                        "why": "For businesses, local testing could help."}]}
    row = writer.ground(raw, [src], set())["stories"][0]
    assert row["what"] == "" and row["headline"].startswith("Scale AI launches") and row["why"]


def test_gossip_and_opinion_sources_are_never_offered_to_the_editor(monkeypatch):
    """Live run 2026-11-13: the editor picked a gossip-worded source for the day's biggest story,
    the check dropped it, and the edition lost the story although clean sources covered it."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    seen = {}

    def fake(key, prompt, system, **kw):
        seen["ids"] = [c["id"] for c in json.loads(prompt)["candidates"]]
        return json.dumps({"stories": [{"id": "s3", "headline": "Nvidia chief executive resigns",
                                        "what": "It paid $3 billion.", "why": ""}]})

    monkeypatch.setattr(writer, "_gemini_generate", fake)
    stories = [_story(1, title="CEO quits over an affair with a colleague"), _story(2, title="Is the AI king finished?"),
               _story(3, title="Nvidia chief executive resigns")]
    out = writer.write_copy(stories, edition="morning", date_label="x", market_facts=[], market_dirs=set(), events=[])
    assert seen["ids"] == ["s3"] and [s["id"] for s in out["stories"]] == ["s3"]


def test_editor_sees_a_fair_spread_of_sources_with_tiers_and_the_edition_brief(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    seen = {}

    def fake(key, prompt, system, **kw):
        seen.update(json.loads(prompt))
        return json.dumps({"stories": [{"id": f"s{i}", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.",
                                        "why": ""} for i in (1, 2, 3)]})

    monkeypatch.setattr(writer, "_gemini_generate", fake)
    monkeypatch.setattr(writer, "RETRY_PAUSE_S", 0)
    stories = []
    for i in range(1, 9):                                   # 8 from one busy desk, then 1 from another
        st = _story(i, title=f"Nvidia sells 250 chips {i}")
        st.source, st.tier = "Busy Desk", 2
        stories.append(st)
    other = _story(9, title="Fed holds rates as shares fall")
    other.source, other.tier, other.channel = "FT", 1, "markets"
    stories.append(other)
    writer.write_copy(stories, edition="morning", date_label="x", market_facts=[], market_dirs=set(), events=[],
                      focus="Morning edition, before Asian markets open.")
    cands = seen["candidates"]
    assert [c["id"] for c in cands] == ["s1", "s2", "s3", "s4", "s9"]        # 4 per source at most
    assert cands[-1] == {"id": "s9", "channel": "markets", "tier": 1, "title": "Fed holds rates as shares fall",
                         "summary": "It paid $3 billion.", "source": "FT", "region": "global"}
    assert seen["edition_brief"].startswith("Morning edition")


def test_no_key_falls_back_to_labelled_wire_copy(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    stories = [_story(i) for i in range(1, 6)] + [_story(7, title="Is AI over?"), _story(8, summary="I think so.")]
    out = writer.write_copy(stories, edition="morning", date_label="x",
                            market_facts=[], market_dirs=set(), events=[])
    assert out["writer"] == "wire" and "GEMINI_API_KEY" in out["writer_note"]
    assert len(out["stories"]) == 2                                            # max 2 per source, no opinion


def test_fallback_editor_takes_over_when_gemini_is_rate_limited(monkeypatch):
    """Live 2026-11-13: Gemini's free tier returned 429 for hours and every edition fell back to raw headlines."""
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("FAKE_KEY", "f")
    monkeypatch.delenv("UNSET_KEY", raising=False)
    monkeypatch.setattr(writer, "_gemini_generate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    calls = []

    def chat(url, key, model, prompt):
        calls.append((url, key, model))
        return '```json\n{"stories": [{"id": "s1", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.", "why": ""}]}\n```'

    monkeypatch.setattr(writer, "_openai_chat", chat)
    writers = [{"name": "skipme", "key_env": "UNSET_KEY", "model": "x", "url": "u0"},
               {"name": "fake", "key_env": "FAKE_KEY", "model": "m1", "url": "u1"}]
    out = writer.write_copy([_story()], edition="morning", date_label="x", market_facts=[], market_dirs=set(),
                            events=[], writers=writers)
    assert out["writer"] == "fake:m1" and calls == [("u1", "f", "m1")]
    assert out["stories"][0]["edited"] is True                         # same fact check, passed


def test_openai_chat_keeps_the_answer_and_drops_thinking_parts(monkeypatch):
    """Live: Mistral returned content as a list of parts (thinking + text), which crashed the parser."""
    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": [
                {"type": "thinking", "thinking": [{"type": "text", "text": "hmm"}]},
                {"type": "text", "text": '{"stories": []}'}]}}]}
    monkeypatch.setattr(writer.httpx, "post", lambda *a, **k: R())
    assert writer._openai_chat("u", "k", "m", "p") == '{"stories": []}'


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
    assert build.pick_edition(at(9, 7, 35), sched) == "morning"      # Monday: a working day for the readers
    assert build.pick_edition(at(13, 7, 35), sched) == "morning"     # Friday
    assert build.pick_edition(at(14, 7, 35), sched) is None          # Saturday: no weekday edition
    assert build.pick_edition(at(9, 20, 40), sched) == "evening"
    assert build.pick_edition(at(14, 20, 40), sched) is None
    assert build.pick_edition(at(15, 9, 0), sched) == "weekly"       # Sunday
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
    assert row["title"] == "US: CPI m/m"

    china = [{"title": "1-y Loan Prime Rate", "country": "CNY", "date": "2026-11-13T09:15:00+08:00", "impact": "High"},
             {"title": "5-y Loan Prime Rate", "country": "CNY", "date": "2026-11-13T09:15:00+08:00", "impact": "High"},
             {"title": "Manufacturing PMI", "country": "CNY", "date": "2026-11-13T09:30:00+08:00", "impact": "Medium"},
             {"title": "CPI y/y", "country": "JPY", "date": "2026-11-13T09:30:00+08:00", "impact": "High"}]
    rows = sources.parse_econ(china, start=now, end=now + dt.timedelta(hours=30), tz=sgt, explain=cal["explain"],
                              countries=cal["countries"])
    assert [r["title"] for r in rows] == ["China: 1-y Loan Prime Rate", "China: Manufacturing PMI"]   # LPR pair = one event
    assert rows[0]["when"] == "Fri 13 Nov, 09:15 Singapore time" and "lending rate" in rows[0]["plain"]

    assert sources.parse_econ([{"title": "NFIB Small Business Optimism", "country": "USD", "impact": "High",
                                "date": "2026-11-12T08:30:00-05:00"},                       # "ism" inside a word
                               {"title": "CPI m/m", "country": "USD", "impact": "High", "date": None}],
                              start=now, end=now + dt.timedelta(hours=30), tz=sgt, explain=cal["explain"]) == []
    (hol,) = sources.parse_econ([{"title": "Bank Holiday", "country": "USD", "impact": "Holiday",
                                  "date": "2026-11-13T00:00:00-05:00"}],
                                start=now, end=now + dt.timedelta(hours=30), tz=sgt, explain=cal["explain"])
    assert hol["when"] == "Fri 13 Nov"                                                      # all-day: no clock time

    nasdaq = {"data": {"rows": [{"symbol": "NVDA", "time": "time-after-hours"}, {"symbol": "ZZZZ", "time": "x"}]}}
    after_close = dt.datetime(2026, 11, 17, 23, 30, tzinfo=UTC)                             # 18:30 New York
    assert sources.parse_earnings(nasdaq, day=dt.date(2026, 11, 17), watchlist=cal["watchlist"], now=after_close) == []
    before = dt.datetime(2026, 11, 17, 12, 0, tzinfo=UTC)                                   # 07:00 New York
    assert len(sources.parse_earnings(nasdaq, day=dt.date(2026, 11, 17), watchlist=cal["watchlist"], now=before)) == 1
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

        "markets": [build.market_block("Wall Street overnight", [q], today=dt.date(2026, 11, 13))],
        "stories": [{**_story().to_dict(), "headline": "H <b>x</b>", "what": "W", "why": "Y", "edited": True,
                     "url": "https://ex.com/?a=1&b='2'"}],
        "outlook": "Watch.", "glossary": [{"term": "GPU", "plain": "A chip."}],
        "events": sources.upcoming_events(dt.date(2027, 5, 30)),
        "calendar": [{"title": "CPI m/m", "when": "Thu 12 Nov, 21:30 Singapore time", "plain": "the US inflation report"}],
        "writer": "gemini", "rejected": [], "problems": ["price for Nikkei unavailable (Timeout)", "news feed 'X' unavailable"],
        "notes": ["price for Nikkei unavailable (Timeout)"],
    }
    return {**ed, **over}


def test_render_html_escapes_untrusted_text_and_shows_everything():
    html = render.render_html(_edition())
    assert "<script>" not in html and "<b>x</b>" not in html
    assert "href='https://ex.com/?a=1&amp;b=&#x27;2&#x27;'" in html           # quote cannot break the attribute
    assert "0.0%" not in html and ">flat<" in html                             # no "-0.0%"
    assert "Why it matters" in html and "AI Channel" in html and "Markets Channel" in html
    assert "Glossary" in html and "The US inflation report." in html
    assert "date not yet confirmed" in html                                    # Computex 2027 flag
    assert "price for Nikkei unavailable" in html                              # degradation is visible
    assert "news feed" not in html                                             # operator noise stays in the log
    assert render.UNSUB_PLACEHOLDER in html
    assert "—" not in html


def test_email_layout_order_and_labels():
    ed = _edition()
    ed["stories"][0]["tag"] = "Industry"
    ed["stories"].append({**ed["stories"][0], "headline": "Second story", "tag": "<b>bad</b>"})
    html = render.render_html(ed)
    ed["stories"].append({**ed["stories"][0], "headline": "Fed holds rates", "channel": "markets", "tag": "Economy"})
    html = render.render_html(ed)
    order = [html.index(x) for x in ("Summary.", "AI Channel", "The wider trend", "Markets Channel", "Market summary",
                                     "Market news", "Fed holds rates", "Looking ahead", "Glossary", "Unsubscribe")]
    assert order == sorted(order)                                  # reading order on a phone
    assert "min&nbsp;read" in html and ">Industry<" in html and "<b>bad</b>" not in html
    assert "padding:12px 0" in html                                # 44px tap targets on links


def test_story_tag_must_come_from_the_fixed_set():
    raw = {"stories": [{"id": "s1", "tag": "Gossip", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.", "why": ""},
                       {"id": "s2", "tag": "Policy", "headline": "Nvidia sells 250 chips", "what": "It paid $3 billion.", "why": ""}]}
    out = writer.ground(raw, [_story(1), _story(2)], set())
    assert [s["tag"] for s in out["stories"]] == ["", "Policy"]


def test_formal_register_no_casual_labels_or_emoji():
    html = render.render_html(_edition())
    for casual in ("Say this at lunch", "Jargon buster", "What it means for you", "30 seconds", "\U0001F1F8"):
        assert casual not in html
    assert "not an official communication of any company" in html and "not investment advice" in html


def test_each_channel_renders_on_its_own():
    ed = _edition()
    ed["stories"].append({**ed["stories"][0], "headline": "Fed holds rates", "channel": "markets"})
    ai, mk = render.render_html(ed, "ai"), render.render_html(ed, "markets")
    assert "AI Channel" in ai and "Markets Channel" not in ai and "Fed holds rates" not in ai and "S&amp;P 500" not in ai
    assert "Markets Channel" in mk and "Fed holds rates" in mk and "S&amp;P 500" in mk and "H &lt;b&gt;x" not in mk
    assert render.UNSUB_PLACEHOLDER in ai and render.UNSUB_PLACEHOLDER in mk
    assert "== MARKETS CHANNEL ==" in render.render_text(ed, "markets") and "== AI CHANNEL ==" not in render.render_text(ed, "markets")


SENSITIVE = writer.sensitive_rules(sources.load_config())


def test_sensitive_story_runs_in_the_publishers_words_without_commentary():
    """Readership rule: no rewrite and no opinion on Huawei, sanctions, export controls or security."""
    src = _story(1, title="US weighs new export controls on AI chips to China",
                 summary="Officials are considering tighter rules, people familiar said.")
    plain = _story(2, title="Google launches glasses", summary="They cost $395.")
    raw = {"hook": "New export controls could reshape the chip trade.", "subject": "Export controls loom, Google launches glasses",
           "big_picture": "AI hardware keeps reaching consumers.", "outlook": "Sanctions may tighten further.",
           "stories": [{"id": "s1", "channel": "ai", "tag": "Policy", "headline": "Washington moves to choke China's AI chips",
                        "what": "The US is tightening the screws.", "why": "For chip makers, this could hurt sales."},
                       {"id": "s2", "channel": "ai", "headline": "Google launches glasses", "what": "They cost $395.", "why": ""}]}
    out = writer.ground(raw, [src, plain], set(), SENSITIVE)
    s1 = out["stories"][0]
    assert s1["verbatim"] and s1["headline"] == src.title and s1["what"] == src.summary and s1["why"] == ""
    assert out["hook"] == "" and out["outlook"] == ""                     # commentary on the topic is refused
    assert out["big_picture"] == "AI hardware keeps reaching consumers."  # unrelated commentary stays
    assert out["subject"] == src.title[:60].rsplit(" ", 1)[0] or out["subject"] == src.title
    html = render.render_html({**_edition(), "stories": [{**s1, "channel": "ai"}]})
    assert "As reported by Src" in html and "Why it matters" not in html
    assert writer.ground({"stories": [{"id": "s9"}]}, [_story(9, title="Huawei unveils new AI chip")], set(), SENSITIVE)["stories"][0]["verbatim"]


def test_sensitive_combinations_and_drafted_copy_are_caught():
    """Live 2026-11-20: 'US signed off on sales of AI chips to China ... Pentagon's list of alleged Chinese
    military-backed companies' named no listed term, was rewritten, and the commentary mentioned export controls."""
    src = _story(1, title="US signed off on sales of nearly 900,000 AI chips to China in six months, House committee says",
                 summary="The US approved shipments of AI chips to companies on the Pentagon's list of alleged Chinese military-backed companies.")
    raw = {"stories": [{"id": "s1", "channel": "ai", "headline": "US approves export of AI chips to Chinese entities",
                        "what": "The US government approved shipments.", "why": "For regulators, this matters."}]}
    row = writer.ground(raw, [src], set(), SENSITIVE)["stories"][0]
    assert row["verbatim"] and row["headline"] == src.title and row["why"] == ""
    # a neutral source, but the editor's own draft strays into a listed topic: also carried verbatim
    plain = _story(2, title="Chip maker reports record quarter", summary="Revenue was $35 billion.")
    raw = {"stories": [{"id": "s2", "headline": "Chip maker reports record quarter", "what": "Revenue was $35 billion.",
                        "why": "For investors, sanctions remain the main risk."}]}
    assert writer.ground(raw, [plain], set(), SENSITIVE)["stories"][0]["verbatim"]
    # ordinary China market news is not swept up
    for ok in ("Hong Kong stocks fall as China tech slides", "China's central bank holds its loan prime rate",
               "Shanghai Composite closes higher on property rally", "Taiwan Weighted index drops 3%"):
        assert not writer._sensitive(ok, SENSITIVE), ok
    for hit in ("China probes US chip maker", "Beijing tightens rare earth export rules", "US-China tensions weigh on shares"):
        assert writer._sensitive(hit, SENSITIVE), hit


def test_index_names_are_not_quantities():
    """Live 2026-11-20: 'Nikkei 225 falls' was rejected because the source said only 'Nikkei'."""
    assert writer.check_story_text("Nikkei 225 falls 2.9% as chip shares drop", "Nikkei Falls 2.9%, Dragged by Chip Stocks") == []
    assert writer.check_story_text("The S&P 500 fell 500 points", "S&P 500 fell 2%")          # a real 500 still counts
    assert writer.check_story_text("Inflation rose in October", "Japan's core inflation accelerates in October") == []


def test_channels_have_a_few_stories_each_ai_first():
    stories = [_story(i, title=f"Nvidia sells 250 chips {i}") for i in range(1, 11)]
    raw = {"stories": [{"id": f"s{i}", "channel": "markets" if i % 2 else "ai", "headline": f"Nvidia sells 250 chips {i}",
                        "what": "It paid $3 billion.", "why": ""} for i in range(1, 11)]
           + [{"id": "s99", "channel": "sports"}]}
    out = writer.ground(raw, stories, set())
    chans = [s["channel"] for s in out["stories"]]
    assert chans == ["ai"] * writer.MAX_AI + ["markets"] * writer.MAX_MARKETS


def test_markets_feed_items_go_to_the_markets_channel(monkeypatch):
    cfg = {"feeds": [{"name": "WSJ", "channel": "markets", "url": "u"}], "ai_keywords": ["ai"],
           "market_keywords": ["shares", "fed"]}
    now = dt.datetime(2026, 11, 12, 12, tzinfo=UTC)
    rss = RSS.replace("OpenAI ships &lt;b&gt;new&lt;/b&gt; model - Reuters", "Shares fall as Fed holds rates")

    class R:
        text = rss; content = rss.encode()
        def raise_for_status(self): pass
    monkeypatch.setattr(sources.httpx, "get", lambda *a, **k: R())
    got = sources.fetch_stories(cfg, since=now - dt.timedelta(days=1), now=now)
    assert [(s.title, s.channel) for s in got] == [("Shares fall as Fed holds rates", "markets")]   # AI plan item skipped


def test_chat_text_per_channel_for_messengers():
    ed = _edition()
    ed["stories"][0].update(tag="Industry", verbatim=False)
    ed["stories"].append({**ed["stories"][0], "headline": "Fed holds rates", "channel": "markets", "verbatim": True})
    fx = sources.Quote("SGD=X", "US dollar in SGD", "", 1.28721, 0.0, 0.0, "2026-11-13", False, fx=True)
    ed["markets"] = [build.market_block("Singapore, last close", [_q("Straits Times Index", -1.3), fx])]
    ai, mk = render.render_chat(ed, "ai"), render.render_chat(ed, "markets")
    assert ai.startswith("Cassandra AI Channel | Morning Edition | Fri 13 Nov 2026")
    assert "1. H <b>x</b>" in ai and "Why it matters: Y" in ai and "Source: Src https://ex.com/?a=1&b='2'" in ai
    assert "Fed holds rates" not in ai and "Straits Times" not in ai
    assert "Singapore, last close (Thu 12 Nov): Straits Times Index -1.3%, US dollar in SGD 1.2872" in mk
    assert "As reported by Src" in mk and "Looking ahead" in mk and "Not investment advice" in mk
    assert "not an official company communication" in ai and render.UNSUB_PLACEHOLDER not in ai + mk
    assert render.render_chat({**ed, "stories": []}, "ai") == ""               # nothing to say: nothing to post


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


def test_currency_rows_do_not_decide_the_session_and_show_the_level():
    """A currency trades round the clock: its newer date must not mark every index as 'last traded' earlier."""
    fx = sources.Quote("CNY=X", "US dollar in yuan", "", 6.66721, 0.01, 0.2, "2026-11-20", True, fx=True)
    block = build.market_block("Greater China, last close", [_q("Shanghai Composite", -0.3, "2026-11-19"), fx])
    assert block["asof"] == "2026-11-19" and not any(r["old"] for r in block["rows"]) and not block["live"]
    live = _q("Shanghai Composite", -1.4, "2026-11-20")
    live.live = True
    now = build.market_block("", [live, _q("Shenzhen Component", -1.8, "2026-11-20")])
    assert now["summary"] == "Shanghai Composite is down (-1.4%). Biggest move: Shenzhen Component is down sharply (-1.8%)."
    assert block["rows"][1]["close"] == "6.6672" and block["summary"] == "Shanghai Composite fell slightly (-0.3%)."


def test_figure_is_withheld_when_two_sources_disagree():
    q = _q("Taiwan Weighted", -8.5)
    q.check, q.check_note = "conflict", "second source shows -3.1%"
    ok = _q("Nikkei 225", -3.8)
    ok.check = "confirmed"
    block = build.market_block("Asia-Pacific today", [ok, q])
    row = block["rows"][1]
    assert row["pct"] is None and row["pct_text"] == "n/a" and "sources disagree" in row["note"]
    assert "Taiwan" not in block["summary"]                       # a withheld figure is never the "biggest move"
    assert (block["confirmed"], block["checked"]) == (1, 1)
    assert "1 of 1 figures confirmed against a second source" in render.render_html(_edition(markets=[block]))


def test_market_tables_follow_the_edition_plan(monkeypatch):
    """Morning: Greater China, Asia-Pacific, Singapore, then Wall Street. Evening: US first, then China's day.
    Titles come from the data: a market that is trading is never called 'last close'."""
    cfg = sources.load_config()
    today = dt.date(2026, 11, 20)
    us = {"S&P 500", "Nasdaq Composite", "Dow Jones", "Semiconductors (SOX)", "Nvidia", "TSMC (US-listed)",
          "S&P 500 futures", "Nasdaq futures"}

    def quotes(asia_date, live=False):
        def fetch(rows, problems=None, as_of=None):
            out = []
            for r in rows:
                q = _q(r["label"], -1.0, "2026-11-19" if r["label"] in us else asia_date)
                q.fx, q.live = bool(r.get("fx")), live and r["label"] not in us
                out.append(q)
            return out
        return fetch

    monkeypatch.setattr(sources, "fetch_quotes", quotes("2026-11-19"))                     # 07:30: nothing open yet
    morning = build.build_markets("morning", cfg, today=today, problems=[])
    assert [b["title"] for b in morning] == ["Greater China, last close", "Asia-Pacific, last close",
                                              "Singapore, last close", "Wall Street overnight"]
    assert morning[0]["rows"][0]["label"] == "Shanghai Composite"

    monkeypatch.setattr(sources, "fetch_quotes", quotes("2026-11-20", live=True))          # a late run at 10:00
    late = build.build_markets("morning", cfg, today=today, problems=[])
    assert [b["title"] for b in late][:3] == ["Greater China, trading now", "Asia-Pacific, trading now",
                                              "Singapore, trading now"]

    monkeypatch.setattr(sources, "fetch_quotes", quotes("2026-11-20"))                     # 20:30: Asia has closed
    evening = build.build_markets("evening", cfg, today=today, problems=[])
    assert [b["title"] for b in evening] == ["Wall Street, last close", "US futures before tonight's open",
                                              "Greater China today", "Singapore today", "Asia-Pacific today"]
    monkeypatch.setattr(sources, "fetch_quotes", quotes("2026-11-19"))                     # an Asian holiday
    holiday = build.build_markets("evening", cfg, today=today, problems=[])
    assert holiday[2]["title"] == "Greater China, last close (no trading today)"
    monkeypatch.setattr(sources, "fetch_quotes", quotes("2026-11-19"))
    monday = build.build_markets("morning", cfg, today=dt.date(2026, 11, 23), problems=[])
    assert monday[3]["title"] == "Wall Street, last close (no US trading overnight)"
    probs: list[str] = []
    monkeypatch.setattr(sources, "fetch_quotes", lambda rows, problems=None, as_of=None: [])
    assert build.build_markets("morning", cfg, today=today, problems=probs) == [] and "no market data" in probs[0]


def test_readers_see_what_affects_them_not_feed_noise():
    probs = ["news feed 'X' unavailable (Timeout)", "news feed 'X' unavailable (Timeout)", "price for CSI 300 unavailable (ValueError)"]
    assert build.reader_notes(probs, 33) == ["price for CSI 300 unavailable (ValueError)"]
    many = [f"news feed 'F{i}' unavailable (Timeout)" for i in range(12)]
    assert build.reader_notes(many, 33) == ["12 of 33 news sources were unavailable, so coverage is thinner than usual"]


def test_monday_morning_looks_back_over_the_weekend(monkeypatch):
    seen = {}
    monkeypatch.setattr(sources, "fetch_quotes", lambda rows, problems=None, as_of=None: [])
    monkeypatch.setattr(sources, "fetch_calendar", lambda *a, **k: [])

    def stories(cfg, since, now, problems=None):
        seen["hours"] = round((now - since).total_seconds() / 3600)
        return []
    monkeypatch.setattr(sources, "fetch_stories", stories)
    build.build_edition("morning", now=dt.datetime(2026, 11, 16, 23, 30, tzinfo=UTC))     # Tue 07:30 SGT
    assert seen["hours"] == 16
    build.build_edition("morning", now=dt.datetime(2026, 11, 15, 23, 30, tzinfo=UTC))     # Mon 07:30 SGT
    assert seen["hours"] == 62


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


def test_as_of_rebuilds_a_past_quote_from_closes_only():
    """A reconstructed edition must show the close as it stood then, never today's live price."""
    day0 = 1793926800                                    # 2026-11-06 09:00 SGT (bar timestamps = session start)
    payload = _chart([100.0, 110.0, 99.0], 120.0, day0 + 5 * 86400)       # meta: a much later live price
    meta = payload["chart"]["result"][0]["meta"]
    meta["regularMarketChangePercent"] = 21.2                            # today's change: must be ignored
    meta["currentTradingPeriod"] = {"regular": {"start": day0, "end": day0 + 8 * 3600}}   # closes 17:00 SGT
    sgt = dt.timezone(dt.timedelta(hours=8))
    before_close = dt.datetime(2026, 11, 8, 12, 0, tzinfo=sgt)          # day 3 still trading
    q = sources.parse_chart(payload, symbol="X", label="X", note="", as_of=before_close)
    assert (q.session_date, q.close, q.live, q.in_hours) == ("2026-11-07", 110.0, False, False)
    assert q.pct_1d == pytest.approx(10.0)
    after_close = dt.datetime(2026, 11, 8, 20, 30, tzinfo=sgt)
    q = sources.parse_chart(payload, symbol="X", label="X", note="", as_of=after_close)
    assert (q.session_date, q.close) == ("2026-11-08", 99.0) and q.pct_1d == pytest.approx(-10.0)


def test_as_of_is_never_sent_and_must_be_in_the_past(capsys):
    from src.briefing import __main__ as cli
    assert cli.main(["--edition", "morning", "--as-of", "2026-11-19 07:30", "--send"]) == 1
    assert cli.main(["--edition", "morning", "--as-of", "2099-01-01 07:30"]) == 1
    assert cli.main(["--edition", "morning", "--as-of", "yesterday"]) == 1
    assert "cannot be sent" in capsys.readouterr().err


def test_sensitive_rules_catch_china_ties_and_political_leaders():
    """Live 2026-11-19: both stories were rewritten by the editor; the Nvidia one lost its China angle."""
    rules = writer.sensitive_rules(sources.load_config())
    assert writer._sensitive("Nvidia faces questions over former No 3's China ties after short seller report", rules)
    assert writer._sensitive("From Shenzhen to Silicon Valley: Xi Jinping calls for global association of bay areas", rules)
    assert not writer._sensitive("Alibaba tops revenue estimates on AI cloud growth", rules)
