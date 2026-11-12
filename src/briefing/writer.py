"""
briefing/writer.py: turn raw stories into plain-English copy for non-technical readers.

The model is an editor, not a source. It picks stories and rewrites them; Python then checks
every piece of copy against the source text (ground()) and throws away anything that contains
a number the source does not contain. Market numbers are never written by the model at all.

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

SYSTEM = """\
You are the editor of a short AI newsletter for busy, NON-TECHNICAL readers in Singapore
(managers, business owners, students, retirees, curious investors). They are smart but do not
know tech jargon. Your job: make real AI news clear, vivid and worth reading.

You get JSON with candidate stories, market facts and upcoming events. Return ONE JSON object:
{
  "subject": "email subject, max 60 characters, makes someone want to open it, no clickbait lies",
  "hook": "1 or 2 sentences that open the email and say why today matters",
  "stories": [
    {"id": "<candidate id>",
     "headline": "punchy rewrite, max 12 words",
     "what": "what happened, 1 or 2 short sentences, plain words",
     "why": "why an ordinary person in Singapore should care, 1 sentence, start with a verb or 'This'"}
  ],
  "market_take": "2 sentences explaining the market mood in everyday language",
  "outlook": "2 or 3 sentences on what to watch next, tied to the events and stories given"
}

Picking stories: choose the 4 to 6 that matter most to an ordinary person. Every story must be
clearly about AI or the AI industry (chips, data centres, AI companies, AI rules, AI and jobs);
if the title alone does not make the AI link clear, skip it. Prefer big moves by well-known
companies, government and policy, jobs, money, everyday products. Include 1 or 2 stories with
region "sg" when good ones are given. Skip niche developer news, rumours and duplicates. Never
pick two candidates about the same event.

Writing rules:
- Explain like a smart friend at a kopitiam. If you must use a technical term, explain it in the
  same sentence. Short sentences. Active voice. No hype words (revolutionary, game-changing).
- FACTS: use only facts that appear in the candidate's title and summary. Never add numbers,
  names, dates or quotes that are not there. If a candidate has only a title, restate the title
  plainly and stop. Copy numbers as digits exactly as the source writes them ("over 250", "$395");
  never spell a number out in words.
- "market_take" and "outlook": do NOT write any digits. The numbers are printed separately.
  Do not predict prices. Do not give buy or sell advice. "outlook" is your reading, so use
  careful words (could, may, watch for).
- Do not use em-dashes or en-dashes.
JSON only. No markdown.
"""

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
# spelled-out quantities would slip past a digits-only check ("two hundred and fifty")
_NUM_WORDS = re.compile(r"\b(?:hundred|thousand|million|billion|trillion|dozen|"
                        r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b", re.I)


def _numbers(text: str) -> set[str]:
    text = text or ""
    digits = {n.replace(",", "").rstrip(".") for n in _NUM.findall(text)}
    return digits | {w.lower() for w in _NUM_WORDS.findall(text)}


def ungrounded(text: str, corpus: str) -> set[str]:
    """Numbers that appear in `text` but nowhere in `corpus`. Empty set = grounded."""
    return _numbers(text) - _numbers(corpus)


def wire_copy(stories: list[Story], reason: str) -> dict[str, Any]:
    """Unedited fallback: newest stories, at most 2 per source, original wording."""
    picked, per_source = [], {}
    for s in stories:
        if per_source.get(s.source, 0) >= 2:
            continue
        per_source[s.source] = per_source.get(s.source, 0) + 1
        picked.append({**s.to_dict(), "headline": s.title, "what": s.summary[:280], "why": "", "edited": False})
        if len(picked) >= MAX_STORIES:
            break
    return {"subject": "", "hook": "", "stories": picked, "market_take": "", "outlook": "",
            "writer": "wire", "writer_note": reason}


def ground(raw: dict[str, Any], stories: list[Story], facts_text: str) -> dict[str, Any]:
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
            bad = ungrounded(text, corpus)
            if bad or not text:
                if bad:
                    rejected.append(f"{src.id}.{field}: numbers not in source {sorted(bad)}")
                text = fallback
                row["edited"] = row["edited"] and field == "why"
            row[field] = text
        out_stories.append(row)

    picked_corpus = " ".join(f"{s['title']} {s['summary']}" for s in out_stories)
    copy: dict[str, Any] = {"stories": out_stories}
    for field, corpus in (("subject", picked_corpus), ("hook", picked_corpus),
                          ("market_take", ""), ("outlook", "")):
        text = lint_no_em_dash(str(raw.get(field) or "").strip())
        bad = ungrounded(text, corpus)
        if bad:
            rejected.append(f"{field}: ungrounded numbers {sorted(bad)}")
            text = ""
        copy[field] = text
    copy["subject"] = copy["subject"][:80]
    copy["rejected"] = rejected
    return copy


def write_copy(stories: list[Story], *, edition: str, date_label: str,
               market_facts: list[str], events: list[dict]) -> dict[str, Any]:
    """Model-edited copy, grounded. Falls back to wire_copy() loudly."""
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
            copy = ground(raw, candidates, " ".join(market_facts))
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
