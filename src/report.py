"""
report.py — Gemini Flash daily report text (LLM narrates; never computes CRS).

Model: gemini-2.5-flash (free tier via ai.google.dev). Migrate before Oct 2026 for image models.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


def _fallback_headline(score: dict[str, Any]) -> str:
    band = score.get("band", "Unknown")
    crs = score.get("crs", "—")
    return f"AI sector in {band} zone — CRS {crs} (template; set GEMINI_API_KEY for live narrative)"


def generate_report_sections(score: dict[str, Any], tier: str = "report") -> dict[str, Any]:
    """
    Return structured report sections for newspaper HTML / email.
    Score dict must come from pipeline/store — LLM only narrates pre-computed numbers.
    """
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return _template_sections(score, tier)

    pages = {"free": 1, "report": 5, "briefing": 10, "agent": 10}.get(tier, 5)
    prompt = _build_prompt(score, tier, pages)
    try:
        text = _gemini_generate(key, prompt)
        return _parse_sections(text, score)
    except Exception as exc:
        sections = _template_sections(score, tier)
        sections["generation_note"] = f"Gemini unavailable: {exc}"
        return sections


def _build_prompt(score: dict[str, Any], tier: str, pages: int) -> str:
    payload = json.dumps({
        "crs": score.get("crs"),
        "band": score.get("band"),
        "fragility": score.get("fragility"),
        "trigger": score.get("trigger"),
        "phase": score.get("phase"),
        "coverage": score.get("coverage"),
        "factors": score.get("factors"),
        "asof": score.get("asof"),
    }, indent=2)
    return f"""You are CASSANDRA, a decision-support research narrator. NEVER invent or recompute CRS, F, T, or factor scores.
Use ONLY the JSON numbers provided. No crash-date predictions. No financial advice. Timing humility required.

Tier: {tier} (~{pages} page equivalent)
Output JSON with keys: headline, sub_headline, col1_html, col2_html, col3_html, caveat
Each col*_html is 2-3 paragraphs of HTML using <p> and <strong> only.

Score JSON:
{payload}
"""


def _gemini_generate(api_key: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
    }
    r = httpx.post(url, params={"key": api_key}, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_sections(raw: str, score: dict[str, Any]) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(raw)
        parsed.setdefault("headline", _fallback_headline(score))
        parsed["score"] = score
        return parsed
    except json.JSONDecodeError:
        return {
            "headline": _fallback_headline(score),
            "sub_headline": raw[:200],
            "col1_html": f"<p>{raw[:800]}</p>",
            "score": score,
        }


def _template_sections(score: dict[str, Any], tier: str) -> dict[str, Any]:
    crs = score.get("crs", "—")
    band = score.get("band", "—")
    f = score.get("fragility", "—")
    t = score.get("trigger", "—")
    cov = score.get("coverage")
    cov_pct = f"{float(cov) * 100:.0f}%" if cov is not None else "—"
    return {
        "headline": f"AI sector enters {band} zone as leverage signals mount",
        "sub_headline": f"Crash Risk Score at {crs}; fragility {f}, trigger {t}",
        "col1_html": (
            f"<p>The system's <strong>Leverage (L)</strong> and <strong>Valuation (V)</strong> factors "
            f"are published on the free tier. CRS reads <strong>{crs}</strong> in the <strong>{band}</strong> band.</p>"
            f"<p>Coverage is <strong>{cov_pct}</strong> — band width reflects missing data honestly.</p>"
        ),
        "col2_html": (
            "<p>The <strong>capex-cut NLP grader</strong> is the primary trigger watch. "
            "No formal hyperscaler capex cut has fired yet.</p>"
            + (
                "<p><strong>S, B, C factors</strong> available on this tier.</p>"
                if tier in ("report", "briefing", "agent")
                else "<p><strong>S, B, C</strong> locked — subscribe at $4.99/mo.</p>"
            )
        ),
        "col3_html": (
            "<p>CASSANDRA reports <strong>loaded spring</strong> conditions, not crash dates. "
            "The interaction term F×T is load-bearing.</p>"
        ),
        "caveat": f"Coverage: {cov_pct} of metrics live. Not investment advice.",
        "tier": tier,
        "score": score,
    }


def render_report_html(sections: dict[str, Any]) -> str:
    """Minimal HTML fragment for email embed."""
    return f"""<article>
<h1>{sections.get('headline', '')}</h1>
<h2>{sections.get('sub_headline', '')}</h2>
{sections.get('col1_html', '')}
{sections.get('col2_html', '')}
{sections.get('col3_html', '')}
<p><em>{sections.get('caveat', '')}</em></p>
<p><small>netie.ai · github.com/Netie-AI/Cassandra</small></p>
</article>"""
