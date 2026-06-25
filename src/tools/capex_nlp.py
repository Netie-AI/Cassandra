"""
capex_nlp.py — grade hyperscaler AI capex-cut language (0–1).

Feeds Trigger (T). LLM grades only; never computes CRS.
Calibration set from HANDOFF_CLAUDE.md — keep in sync with Claude reviews.
"""
from __future__ import annotations

import json
import os
import re

import httpx

CAPEX_CUT_CALIBRATION = [
    {
        "id": "cc_01",
        "snippet": (
            "Given meaningfully weaker-than-expected enterprise AI adoption, we are "
            "reducing our full-year fiscal 2026 capital expenditure guidance to "
            "approximately $68 billion, down from our prior estimate of $80 billion. "
            "We are pausing planned Azure data center expansions in EMEA and APAC."
        ),
        "expected_score": 0.93,
    },
    {
        "id": "cc_02",
        "snippet": (
            "We have made the decision to significantly curtail our data center "
            "infrastructure investment plans for the remainder of the calendar year."
        ),
        "expected_score": 0.86,
    },
    {
        "id": "cc_03",
        "snippet": (
            "We are moderating the pace of near-term deployment given the current "
            "demand environment. Certain projects have shifted to the right by one to "
            "two quarters."
        ),
        "expected_score": 0.71,
    },
    {
        "id": "cc_04",
        "snippet": (
            "Our capital deployment will remain data-driven, and we have flexibility in "
            "the timing of certain projects."
        ),
        "expected_score": 0.55,
    },
    {
        "id": "cc_05",
        "snippet": (
            "We remain fully committed to our infrastructure investment plan while being "
            "thoughtful about pacing to ensure we're deploying capital efficiently."
        ),
        "expected_score": 0.42,
    },
    {
        "id": "cc_06",
        "snippet": (
            "Our capital expenditure guidance for 2025 remains unchanged at "
            "approximately $105 billion."
        ),
        "expected_score": 0.22,
    },
    {
        "id": "cc_07",
        "snippet": (
            "We remain on track with our global data center build-out. Customer "
            "demand for Google Cloud and AI services continues to be strong."
        ),
        "expected_score": 0.14,
    },
    {
        "id": "cc_08",
        "snippet": (
            "Capital expenditure for fiscal year 2025 is expected to be approximately "
            "$80 billion, consistent with our prior guidance."
        ),
        "expected_score": 0.08,
    },
    {
        "id": "cc_09",
        "snippet": (
            "We are accelerating our data center investments, committed to an additional "
            "$15 billion in AWS infrastructure spending beyond our original plan."
        ),
        "expected_score": 0.04,
    },
    {
        "id": "cc_10",
        "snippet": (
            "We are doubling our TPU cluster investments and have raised our "
            "five-year AI infrastructure commitment to $250 billion."
        ),
        "expected_score": 0.02,
    },
]

RUBRIC = """Score hyperscaler AI/datacenter capex-cut signal 0.0–1.0.
0.80–1.0 FIRE: explicit guidance cut, pauses, dollar reductions
0.55–0.79 CONCERN: pace moderation, flexible timing, demand shortfall
0.35–0.54 AMBIGUOUS: mixed commitment + caveats
0.15–0.34 NEUTRAL: unchanged guidance, minor caution
0.00–0.14 GROWTH: capex raise, acceleration
Forward-looking language only. Non-AI capex → 0.0.
Respond ONLY: {"score":0.XX,"reason":"one sentence"}"""


def _few_shot_block() -> str:
    lines = []
    for ex in CAPEX_CUT_CALIBRATION[:6]:
        lines.append(f'Snippet: "{ex["snippet"][:180]}..." → {ex["expected_score"]}')
    return "\n".join(lines)


def _parse_score(text: str) -> tuple[float, str]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        return float(data["score"]), str(data.get("reason", ""))
    except (json.JSONDecodeError, KeyError, TypeError):
        m = re.search(r'"score"\s*:\s*([0-9.]+)', text)
        if m:
            return float(m.group(1)), text[:120]
    return 0.5, "parse failure — default neutral"


def score_capex_cut(snippet: str) -> tuple[float, str]:
    """Grade a single earnings snippet. Returns (score, reason)."""
    if not snippet or not snippet.strip():
        return 0.0, "empty snippet"

    prompt = f"{RUBRIC}\n\nExamples:\n{_few_shot_block()}\n\nSnippet:\n{snippet.strip()}"

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return _call_gemini(prompt, gemini_key)

    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return _call_openrouter(prompt, or_key)

    return 0.5, "no LLM key — default neutral"


def _call_gemini(prompt: str, api_key: str) -> tuple[float, str]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 120},
    }
    r = httpx.post(url, params={"key": api_key}, json=body, timeout=45)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_score(text)


def _call_openrouter(prompt: str, api_key: str) -> tuple[float, str]:
    model = os.getenv("OPENROUTER_SUBAGENT_MODEL", "anthropic/claude-sonnet-4")
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "max_tokens": 120, "temperature": 0.1,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=45,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _parse_score(text)
