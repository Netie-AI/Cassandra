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
        "source": "Microsoft Q2 2026 earnings call (synthetic calibration example)",
        "snippet": (
            "Given meaningfully weaker-than-expected enterprise AI adoption, we are "
            "reducing our full-year fiscal 2026 capital expenditure guidance to "
            "approximately $68 billion, down from our prior estimate of $80 billion. "
            "We are pausing planned Azure data center expansions in EMEA and APAC "
            "and will reassess the pace of deployment based on Q3 demand signals."
        ),
        "expected_score": 0.93,
        "reasoning": (
            "Explicit dollar-figure reduction ($80B→$68B), named region pauses, "
            "and formal guidance cut. Maximum fire signal."
        ),
    },
    {
        "id": "cc_02",
        "source": "Amazon Q4 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We have made the decision to significantly curtail our data center "
            "infrastructure investment plans for the remainder of the calendar year. "
            "The pace of AI workload growth has not met our internal expectations, "
            "and we believe the prudent course is to slow our build-out materially "
            "until we have better visibility on capacity utilization rates."
        ),
        "expected_score": 0.86,
        "reasoning": (
            "Strong cut language ('curtail', 'slow materially') and explicit demand "
            "shortfall admission. No hard dollar figure but forward-looking reduction."
        ),
    },
    {
        "id": "cc_03",
        "source": "Google Q1 2026 earnings call (synthetic calibration example)",
        "snippet": (
            "We're being more disciplined about the timing of our TPU and data center "
            "investments. While we still expect to hit our multi-year build targets, "
            "we are moderating the pace of near-term deployment given the current "
            "demand environment. Certain projects have shifted to the right by one to "
            "two quarters."
        ),
        "expected_score": 0.71,
        "reasoning": (
            "Clear moderation language ('moderating pace', 'shifted to the right') "
            "without explicit guidance cut. Projects delayed, not cancelled. Mid-range "
            "concern signal."
        ),
    },
    {
        "id": "cc_04",
        "source": "Meta Q3 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We continue to monitor our AI infrastructure capacity utilization closely. "
            "Our capital deployment will remain data-driven, and we have flexibility in "
            "the timing of certain projects. We've asked our teams to rigorously "
            "prioritize their investment requests given the macro environment."
        ),
        "expected_score": 0.55,
        "reasoning": (
            "Ambiguous — 'monitoring closely', 'flexibility in timing', 'prioritize' "
            "all suggest caution but no formal change. Sits at the concern/ambiguous "
            "boundary. Trend watching required."
        ),
    },
    {
        "id": "cc_05",
        "source": "Microsoft Q3 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "While we're watching demand signals carefully, we remain fully committed "
            "to our infrastructure investment plan. We believe these investments are "
            "critical for long-term competitiveness in AI. That said, we are being "
            "thoughtful about pacing to ensure we're deploying capital efficiently."
        ),
        "expected_score": 0.42,
        "reasoning": (
            "Mixed: 'committed' directly contradicts 'thoughtful about pacing'. "
            "Ambiguous mid-range. No actionable cut signal yet."
        ),
    },
    {
        "id": "cc_06",
        "source": "Amazon Q2 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "Our capital expenditure guidance for 2025 remains unchanged at "
            "approximately $105 billion. We have high confidence in the long-term "
            "demand trajectory for AWS. We'll continue to stay disciplined as always "
            "in how we deploy capital."
        ),
        "expected_score": 0.22,
        "reasoning": (
            "Explicit 'unchanged' guidance confirmation. 'High confidence' framing. "
            "Boilerplate 'disciplined' does not constitute a signal. Low score."
        ),
    },
    {
        "id": "cc_07",
        "source": "Google Q2 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We remain on track with our global data center build-out. Customer "
            "demand for Google Cloud and AI services continues to be strong, and "
            "we're focused on meeting our commitments. We continue to evaluate "
            "the best ways to optimize our investment efficiency."
        ),
        "expected_score": 0.14,
        "reasoning": (
            "'On track', 'demand strong', 'meeting commitments'. Purely positive "
            "maintenance language. 'Optimize efficiency' is generic. Near-zero signal."
        ),
    },
    {
        "id": "cc_08",
        "source": "Microsoft Q1 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "Capital expenditure for fiscal year 2025 is expected to be approximately "
            "$80 billion, consistent with our prior guidance. We are expanding capacity "
            "across Azure regions to meet robust customer demand for AI services."
        ),
        "expected_score": 0.08,
        "reasoning": (
            "Flat 'consistent with prior guidance' + 'expanding capacity'. "
            "Pure maintenance signal. No concern language whatsoever."
        ),
    },
    {
        "id": "cc_09",
        "source": "Amazon Q1 2025 earnings call (synthetic calibration example)",
        "snippet": (
            "We are accelerating our data center investments in response to "
            "demand that has exceeded our forecasts. We've committed to an additional "
            "$15 billion in AWS infrastructure spending beyond our original plan, "
            "bringing full-year capex to approximately $120 billion."
        ),
        "expected_score": 0.04,
        "reasoning": (
            "Explicit acceleration + guidance raise. Strong bullish capex signal. "
            "Opposite of what we're detecting. Nearly zero cut signal."
        ),
    },
    {
        "id": "cc_10",
        "source": "Google Q4 2024 earnings call (synthetic calibration example)",
        "snippet": (
            "The AI opportunity is generational, and we intend to be the clear global "
            "leader. We are doubling our TPU cluster investments and have raised our "
            "five-year AI infrastructure commitment to $250 billion. We are deploying "
            "at the fastest pace in Google's history."
        ),
        "expected_score": 0.02,
        "reasoning": (
            "Maximum bullish signal: 'doubling', 'generational', '$250B commitment', "
            "'fastest pace in history'. Absolute zero on cut detection."
        ),
    },
]

RUBRIC = """
Score this earnings call snippet for AI/datacenter capex cut signal (0.0–1.0).

RUBRIC:
0.80–1.0: Explicit guidance cut, named pauses, dollar reductions (FIRE)
0.55–0.79: Pace moderation, 'flexible timing', demand shortfall (CONCERN)
0.35–0.54: Mixed commitment with notable caveats (AMBIGUOUS)
0.15–0.34: Standard unchanged guidance, minor caution (NEUTRAL)
0.00–0.14: Capex growth, raised guidance, acceleration (GROWTH)

Rules: Score FORWARD-LOOKING language only.
Only score hyperscaler AI/datacenter capex. Non-AI capex → 0.0.

Edge cases:
- Past-tense cuts ("we reduced last quarter") → subtract 0.15 from score
- Retail/logistics capex (warehouses, stores, delivery) → return 0.0 immediately
- Mixed call (AI up, non-AI down) → score AI segment only
- Leaked/rumour language ("reportedly pausing") → cap at 0.60 regardless

Respond with ONLY a JSON object: {"score": 0.XX, "reason": "one sentence"}
"""

GRADER_SYSTEM = RUBRIC

_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


def _few_shot_block() -> str:
    lines = ["Few-shot examples:"]
    for ex in CAPEX_CUT_CALIBRATION:
        lines.append(
            f'[{ex["id"]}] score={ex["expected_score"]} snippet="{ex["snippet"][:200]}..."'
        )
    return "\n".join(lines)


def _parse_score(text: str) -> float:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        return float(data["score"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        m = re.search(r'"score"\s*:\s*([0-9.]+)', text)
        if m:
            return float(m.group(1))
    return 0.5


def score_capex_cut(snippet: str) -> float:
    """Grade a single earnings snippet. Returns 0.0–1.0; parse failure → 0.5."""
    if not snippet or not snippet.strip():
        return 0.0

    user_prompt = f"{_few_shot_block()}\n\nSnippet to score:\n{snippet.strip()}"

    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return _call_openrouter(user_prompt, or_key)

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return _call_gemini(user_prompt, gemini_key)

    return 0.5


def score_capex_cut_detail(snippet: str) -> tuple[float, str]:
    """Grade snippet; returns (score, note) for pipeline logging."""
    if not snippet or not snippet.strip():
        return 0.0, "empty snippet"
    score = score_capex_cut(snippet)
    if score == 0.5 and not os.getenv("OPENROUTER_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        return score, "no LLM key — default neutral"
    return score, "graded"


def _call_openrouter(user_prompt: str, api_key: str) -> float:
    model = os.getenv("OPENROUTER_SUBAGENT_MODEL", _DEFAULT_MODEL)
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "max_tokens": 100,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": GRADER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=45,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _parse_score(text)


def _call_gemini(user_prompt: str, api_key: str) -> float:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": GRADER_SYSTEM}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
    }
    r = httpx.post(url, params={"key": api_key}, json=body, timeout=45)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_score(text)
