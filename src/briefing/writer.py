"""
briefing/writer.py: turn raw stories into plain-English copy for non-technical readers.

The model is an editor, not a source. It picks stories and rewrites them; Python then checks
every piece of copy against the source text (check_story_text / check_free_text) and falls
back to the publisher's wording when a check fails. Market numbers are never written by the model.

What the checks catch: numbers and their units, spelled-out quantities, up/down direction,
dropped denials or "reportedly", invented quotes, advice words, market mood that contradicts
the data. What they cannot catch: a wrong name or a wrong claim that has no such marker, so
every story always carries its source link.

No GEMINI_API_KEY, or every model fails -> wire_copy(): original headlines, labelled as such.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from src.report import _gemini_generate
from src.tools.copy_lint import lint_no_em_dash

from .sources import Story

DEFAULT_MODELS = "gemini-3.8-flash,gemini-3.5-flash,gemini-flash-latest"
MAX_STORIES = 6
MAX_CANDIDATES = 40
RETRY_PAUSE_S = 20
SUBJECT_MAX = 60

SYSTEM = """\
You edit a short AI newsletter for busy, NON-TECHNICAL readers in Singapore (managers, shop and
business owners, students, retirees, first-time investors). They are smart, short of time, and
do not know tech or finance jargon. Make real AI news clear, lively and worth forwarding.

You get JSON: candidate stories, market facts, upcoming events. Return ONE JSON object:
{
 "subject": "max 55 characters. Lead with the single most surprising fact, then a second hook after a comma. No newsletter name, no date.",
 "hook": "2 sentences. First: the biggest story in plain words. Second: what else is inside. Speak to 'you'.",
 "big_picture": "1 or 2 sentences linking today's stories into one trend. No digits.",
 "stories": [{"id": "<candidate id>",
   "headline": "max 10 words, concrete subject and active verb",
   "what": "1 or 2 short sentences, plain words",
   "why": "1 sentence starting with 'If you' or 'For', naming who is affected (shoppers, employees, business owners, savers, students) and how"}],
 "talking_point": "One sentence a reader could repeat at lunch, about the first story only.",
 "market_take": "2 sentences on the market mood in everyday language",
 "outlook": "2 sentences on what to watch next, tied to on_the_calendar_next and upcoming_events. Do not repeat their descriptions."
}

Picking: choose the 4 to 6 stories that matter most to an ordinary person, biggest first.
Each must clearly be about AI or the AI industry (chips, data centres, AI companies, rules,
jobs); if the title alone does not show the AI link, skip it. Prefer well-known companies,
government, jobs, money, everyday products. Include 1 or 2 with region "sg" when good ones
exist. Skip developer news, rumours, opinion columns and duplicates. Never pick two
candidates about the same event.

Respect, never broken:
- Report what a person did in their job (resigned, was appointed, was charged, announced).
  Never repeat claims about anyone's private life (relationships, affairs, family, health,
  looks), even if the source does. Say "after a scandal" or "after allegations" at most.
- Never mock, shame or insult a person, a company or a group. No sarcasm about people.
- Skip stories that are mainly gossip, personal attacks, opinion rants or insults.
- Skip video-game and entertainment news unless the story is really about AI.
- "talking_point" must be a useful fact or idea, never gossip about a person.

Voice: a well-read friend at a kopitiam. Short sentences. Active voice. Everyday comparisons
are welcome if they add no facts. Explain any technical or finance term in the same sentence.
No hype or filler (revolutionary, game-changing, shockwaves, landscape).

Accuracy, never broken:
- Use only facts in that candidate's title and summary. Never add numbers, names, dates,
  quotes, causes or reactions that are not there. If a candidate has only a title, restate
  it plainly and stop.
- Copy numbers as digits with their unit exactly as written ("over 250", "$395", "$3 billion").
  Never spell them out, convert currency or round.
- Keep the direction (rose or fell) and keep any doubt in the source (denies, reportedly, rumour).
- "why", "big_picture", "talking_point": word consequences as possible (could, may).
- "market_take", "outlook", "big_picture": NO digits. Describe direction only as market_facts
  show it; if an index moved less than 0.2%, call it flat. Do not say a story caused a market
  move. No price predictions. No buy or sell advice. Use careful words (could, may, watch for).
- No em-dashes or en-dashes.
JSON only. No markdown.
"""

# -- fact-check primitives ---------------------------------------------------
_UNIT = {"%": "pct", "percent": "pct", "per cent": "pct", "k": "k", "thousand": "k", "m": "m", "mn": "m",
         "million": "m", "b": "b", "bn": "b", "billion": "b", "tn": "t", "trillion": "t"}
_NUM = re.compile(r"(?<![A-Za-z])((?:US|S|A|HK|NT|C)?\$|£|€|¥)?(\d[\d,]*(?:\.\d+)?)"
                  r"(?:\s?(%)|\s?(percent|per cent|thousand|million|billion|trillion|mn|bn|tn|k|m|b)\b)?", re.I)
_NUM_WORDS = re.compile(
    r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundreds?|"
    r"thousands?|millions?|billions?|trillions?|dozens?|half|halved|doubl\w+|tripl\w+)\b", re.I)
# "up 8%" / "down 8%" count as direction words only when a figure follows ("sign up" must not).
_UP = re.compile(r"\b(?:rose|rises?|risen|rising|soar\w*|jump\w*|gain\w*|surg\w*|climb\w*|rall(?:y|ied|ies)|"
                 r"higher|grew|grows?|increas\w+|rebound\w*|spik\w+|up\s+(?:by\s+)?[\d$£€])", re.I)
_DOWN = re.compile(r"\b(?:fell|falls?|fallen|falling|drop\w*|slump\w*|plung\w*|slid\w*|slip\w*|tumbl\w*|"
                   r"declin\w*|sank|sinks?|sinking|crash\w*|lower|lost|loses?|losing|shed|shrank|shrink\w*|"
                   r"dip(?:s|ped|ping)?|plummet\w*|decreas\w+|collaps\w+|down\s+(?:by\s+)?[\d$£€])", re.I)
# Hedges in a HEADLINE that make the claim less than a done fact. Copy must keep one of them.
# Looked up in the source title only: a stray "could" or "not" deep in a summary is not a hedge
# on the main claim, and demanding it there rejected most faithful rewrites.
_DOUBT = re.compile(r"\b(?:den(?:y|ies|ied)|rejects?|rejected|turns? down|rules? out|refut\w+|rumou?r\w*|"
                    r"reportedly|unconfirmed|alleged\w*|accus\w+|may|might|could|in talks|consider\w*|"
                    r"weigh(?:s|ing)?|plans? to|planning to|expected to|said to|scraps?|scrapped|"
                    r"will not|does not|did not|has not|no plans?)\b|\b(?:wo|does|did|has|is)n['\u2019]t\b", re.I)
_QUOTE = re.compile(r"[\"\u201c]([^\"\u201d]{8,})[\"\u201d]")
_ADVICE = re.compile(r"\b(?:buy|sell|purchase|invest in|avoid|dump|load up|steer clear|go short|"
                     r"guarantee[ds]?|certain(?:ly)?|definitely|"
                     r"will (?:rise|fall|crash|soar|double|surge|slump|drop|jump|cut|raise|hike))\b", re.I)
_CAUSE = re.compile(r"\b(?:because of|due to|thanks to|caused by|driven by|as a result of|after the)\b", re.I)
# Private-life gossip and insults. The newsletter reports what people did in their jobs.
# Kept narrow on purpose: "Ministry of Home Affairs", "nude image ban" and "winners and losers" are news.
_DISRESPECT = re.compile(
    r"\b(?:extramarital|mistress\w*|love child|affairs? scandals?|affair with|"
    r"(?:his|her|their|an|secret|alleged|second) affairs?|cheat(?:ed|ing) on|girlfriends?|boyfriends?|"
    r"divorc\w+|pathetic|idiots?|idiotic|stupid|morons?|clowns?|humiliat\w+|ugly)\b", re.I)


def disrespectful(text: str) -> bool:
    """True when copy gossips about someone's private life or insults them."""
    return bool(_DISRESPECT.search(text or ""))


def _numbers(text: str) -> set:
    """Every quantity in the text as (value, unit), plus spelled-out quantity words."""
    out: set = set()
    for cur, value, pct, unit in _NUM.findall(text or ""):
        cur = "$" if cur.upper() == "US$" else cur.upper()      # "$3bn" is not "S$3bn" or "£3bn"
        try:
            out.add((float(value.replace(",", "")), cur + _UNIT.get((pct or unit).lower(), "")))
        except ValueError:
            out.add((value, cur))
    rest = _NUM.sub(" ", text or "")          # "3 billion" is already counted above as (3, b)
    return out | {w.lower() for w in _NUM_WORDS.findall(rest)}


def ungrounded(text: str, corpus: str) -> set:
    """Quantities in `text` that are absent from `corpus` (same value AND same unit). Empty = grounded."""
    return _numbers(text) - _numbers(corpus)


def check_story_text(text: str, corpus: str, *, title: str | None = None) -> list[str]:
    """Reasons this copy is not supported by its source text. Empty list = passes.
    `title`: the source headline; when it hedges its claim (denies, may, in talks), the copy must too."""
    why = []
    bad = ungrounded(text, corpus)
    if bad:
        why.append(f"numbers not in source {sorted(map(str, bad))}")
    if _UP.search(text) and not _UP.search(corpus):
        why.append("says something rose, source does not")
    if _DOWN.search(text) and not _DOWN.search(corpus):
        why.append("says something fell, source does not")
    if title and _DOUBT.search(title) and not _DOUBT.search(text):
        why.append("dropped the source's denial or doubt")
    low = corpus.lower()
    if any(q.lower().strip(" .,") not in low for q in _QUOTE.findall(text)):
        why.append("quote not in source")
    return why


def check_spanning(text: str, corpora: list[str]) -> list[str]:
    """For copy that covers several stories (subject, hook): every clause must be fully supported
    by ONE story, so a number from one story cannot be glued to the company from another."""
    why = []
    for clause in re.split(r"(?<=[.!?;])\s+|,\s+(?:and|plus|while|as)\s+|\s+plus\s+|,\s+", text):
        clause = clause.strip()
        if clause and corpora and all(check_story_text(clause, c) for c in corpora):
            why.append(f"no single story supports: {clause[:60]!r}")
    return why


def check_free_text(text: str, market_dirs: set[str] | None = None) -> list[str]:
    """Checks for commentary fields: no quantities, no advice or certainty, mood must match the data."""
    why = []
    if _numbers(text):
        why.append("contains numbers")
    if _ADVICE.search(text):
        why.append("contains advice or certainty wording")
    if market_dirs is not None:
        if _CAUSE.search(text):
            why.append("claims a cause for a market move")
        if _UP.search(text) and "up" not in market_dirs:
            why.append("says markets rose, data shows no riser")
        if _DOWN.search(text) and "down" not in market_dirs:
            why.append("says markets fell, data shows no faller")
    return why


def _clip(text: str, limit: int) -> str:
    """Cut at a word boundary so a number is never sliced in half."""
    if len(text) <= limit:
        return text
    return text[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:")


def _is_opinion(s: Story) -> bool:
    return s.title.rstrip().endswith("?") or s.summary.startswith(("I ", "I'", "My "))


def wire_copy(stories: list[Story], reason: str) -> dict[str, Any]:
    """Unedited fallback: newest news stories, at most 2 per source, original wording."""
    picked, per_source = [], {}
    for s in stories:
        if per_source.get(s.source, 0) >= 2 or _is_opinion(s) or disrespectful(f"{s.title} {s.summary}"):
            continue
        per_source[s.source] = per_source.get(s.source, 0) + 1
        picked.append({**s.to_dict(), "headline": s.title, "what": _clip(s.summary, 280), "why": "",
                       "edited": False})
        if len(picked) >= MAX_STORIES:
            break
    return {"subject": "", "hook": "", "big_picture": "", "talking_point": "", "stories": picked,
            "market_take": "", "outlook": "", "writer": "wire", "writer_note": reason, "rejected": []}


def ground(raw: dict[str, Any], stories: list[Story], market_dirs: set[str]) -> dict[str, Any]:
    """Validate model output against sources. Returns clean copy + a list of what was rejected."""
    by_id = {s.id: s for s in stories}
    rejected: list[str] = []
    out_stories: list[dict[str, Any]] = []
    for item in (raw.get("stories") or [])[:MAX_STORIES]:
        src = by_id.pop(str(item.get("id", "")), None) if isinstance(item, dict) else None
        if src is None:                                   # unknown or repeated id: invented story
            rejected.append("story with unknown id dropped")
            continue
        corpus = f"{src.title} {src.summary}"
        row = {**src.to_dict(), "edited": True}
        for field, fallback in (("headline", src.title), ("what", src.summary), ("why", "")):
            text = lint_no_em_dash(str(item.get(field) or "").strip())
            if field == "why":       # a possible consequence: must not state new facts or advice
                bad = check_story_text(text, corpus)
                if _ADVICE.search(text):
                    bad.append("contains advice or certainty wording")
            else:
                bad = check_story_text(text, corpus, title=src.title)
            if disrespectful(text):
                bad.append("gossip or insult wording")
            if bad or not text:
                rejected += [f"{src.id}.{field}: {b}" for b in bad]
                text = fallback
                row["edited"] = row["edited"] and field == "why"
            row[field] = text
        # the publisher's own wording can be the problem: then the story does not run at all
        if disrespectful(f"{row['headline']} {row['what']}"):
            rejected.append(f"{src.id}: dropped, only available wording is gossip or insult")
            continue
        out_stories.append(row)

    copy: dict[str, Any] = {"stories": out_stories}
    pooled = " ".join(f"{s['title']} {s['summary']}" for s in out_stories)
    first = f"{out_stories[0]['title']} {out_stories[0]['summary']}" if out_stories else ""

    def take(field: str, reasons_for) -> None:
        text = lint_no_em_dash(str(raw.get(field) or "").strip())
        if field == "subject":
            text = _clip(text, SUBJECT_MAX)
        bad = reasons_for(text) if text else []
        if disrespectful(text):
            bad.append("gossip or insult wording")
        rejected.extend(f"{field}: {b}" for b in bad)
        copy[field] = "" if bad else text

    corpora = [f"{s['title']} {s['summary']}" for s in out_stories]
    take("subject", lambda t: check_spanning(t, corpora))
    take("hook", lambda t: check_spanning(t, corpora))
    take("talking_point", lambda t: check_story_text(t, first, title=out_stories[0]["title"] if out_stories else None))
    take("big_picture", check_free_text)
    take("outlook", check_free_text)
    take("market_take", lambda t: check_free_text(t, market_dirs))
    if any(": dropped," in r for r in rejected):
        # the opening lines were written for a line-up that no longer exists
        copy["hook"] = copy["big_picture"] = ""
        copy["subject"] = _clip(out_stories[0]["headline"], SUBJECT_MAX) if out_stories else ""
        rejected.append("subject and hook rebuilt: a picked story was dropped")
    copy["rejected"] = rejected
    return copy


def write_copy(stories: list[Story], *, edition: str, date_label: str, market_facts: list[str],
               market_dirs: set[str], events: list[dict], calendar: list[dict] | None = None) -> dict[str, Any]:
    """Model-edited copy, fact-checked. Falls back to wire_copy() loudly."""
    if not stories:
        return wire_copy([], "no stories in the window")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return wire_copy(stories, "GEMINI_API_KEY not set")

    candidates = stories[:MAX_CANDIDATES]
    prompt = json.dumps({
        "edition": edition,
        "date": date_label,
        "candidates": [{"id": s.id, "title": s.title, "summary": s.summary[:400],
                        "source": s.source, "region": s.region} for s in candidates],
        "market_facts": market_facts,
        "upcoming_events": [{"name": e["name"], "in_days": e["days_away"], "why": e["why"]} for e in events],
        "on_the_calendar_next": [{"what": c["title"], "meaning": c["plain"]} for c in (calendar or [])],
    }, ensure_ascii=False)

    errors: list[str] = []
    models = [m.strip() for m in os.getenv("GEMINI_BRIEFING_MODELS", DEFAULT_MODELS).split(",") if m.strip()]
    for i, model in enumerate(models * 2):               # two passes: 503 "overloaded" is usually brief
        if i == len(models):
            time.sleep(RETRY_PAUSE_S)
        try:
            text = _gemini_generate(key, prompt, SYSTEM, model=model, max_tokens=8192,
                                    temperature=0.3, json_mode=True, timeout=120)
            raw = json.loads(text)
            if not isinstance(raw, dict):
                raise ValueError("model did not return a JSON object")
            copy = ground(raw, candidates, market_dirs)
            if len(copy["stories"]) < min(3, len(candidates)):
                raise ValueError(f"only {len(copy['stories'])} usable stories")
            copy["writer"] = model
            copy["writer_note"] = ""
            return copy
        except Exception as exc:
            # never str(exc): httpx errors embed the request URL, which carries the API key
            status = getattr(getattr(exc, "response", None), "status_code", "")
            errors.append(f"{model}: {type(exc).__name__} {status}".strip())
    return wire_copy(stories, "AI editor unavailable: " + "; ".join(errors)[-300:])
