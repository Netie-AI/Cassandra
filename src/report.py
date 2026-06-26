"""
report.py — Gemini Flash daily report text (LLM narrates; never computes CRS).

Model: gemini-2.5-flash (free tier via ai.google.dev). Migrate before Oct 2026 for image models.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .tools.copy_lint import lint_dict_strings, lint_no_em_dash

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

_SECTION_KEYS = (
    "headline", "sub_headline", "col1_html", "col2_html", "col3_html", "caveat", "markdown",
)

REPORT_SYSTEM = """\
You write Cassandra's Daily, a short market risk brief for humans.
Markdown only. Warm, direct, institutional tone. No hedging filler.
Do not use em-dashes or en-dashes. Use commas or periods instead.

Sections (exact headers):
## Signal
## Structure
## Risk

Each section: exactly 3 bullets. Max 18 words per bullet.
Never print the CRS number. Say the band name only (e.g. Awareness, Mania).
Never predict crash dates. Never give trade advice.
Input is pre-computed JSON. Interpret it, do not repeat raw fields.
Name sources when the input includes them.
"""

TRANSLATE_SYSTEM = """\
Translate the Cassandra market brief into {lang_name}.
Keep the same meaning and structure. Natural newsroom tone, not robotic machine translation.
Do not use em-dashes or en-dashes. Use commas or periods instead.
Return JSON only with keys: headline, sub_headline, col1_html, col2_html, col3_html, caveat.
Preserve HTML tags exactly.
"""

GATE_SYSTEM = """\
You QA translated financial copy. Check: natural tone, correct finance terms, no em-dashes.
If the translation passes, return the same JSON unchanged.
If it fails, return a corrected JSON with the same keys.
JSON only.
"""


def _lint_sections(sections: dict[str, Any]) -> dict[str, Any]:
    return lint_dict_strings(dict(sections), _SECTION_KEYS)


def generate_report_sections(
    score: dict[str, Any],
    tier: str = "report",
    *,
    edition_context: str | None = None,
) -> dict[str, Any]:
    """
    Return structured report sections for newspaper HTML / email (English canonical).
    Score dict must come from pipeline/store. LLM only narrates pre-computed numbers.
    """
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return _lint_sections(_template_sections(score, tier))

    prompt = _build_prompt(score, tier, edition_context=edition_context)
    try:
        from .tools.persona import load_cassandra_persona

        system = f"{load_cassandra_persona(max_chars=1200)}\n\n{REPORT_SYSTEM}"
        if edition_context:
            system = f"{system}\n\nEdition framing:\n{edition_context}"
        text = _gemini_generate(key, prompt, system)
        return _lint_sections(_parse_sections(text, score))
    except Exception as exc:
        sections = _template_sections(score, tier)
        sections["generation_note"] = f"Gemini unavailable: {exc}"
        return _lint_sections(sections)


def generate_report_multilingual(
    score: dict[str, Any],
    tier: str = "report",
    *,
    edition_context: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Generate EN canonical edition, then ZH + MS translations. All linted."""
    en = generate_report_sections(score, tier, edition_context=edition_context)
    out: dict[str, dict[str, Any]] = {"en": en}
    api_key = os.getenv("GEMINI_API_KEY")
    for lang, lang_name in (("zh", "Simplified Chinese"), ("ms", "Malay")):
        if api_key:
            try:
                out[lang] = _translate_sections(api_key, en, lang_name)
            except Exception:
                out[lang] = _lint_sections(_fallback_translation(en, lang))
        else:
            out[lang] = _lint_sections(_fallback_translation(en, lang))
    return out


def _build_prompt(
    score: dict[str, Any],
    tier: str,
    *,
    edition_context: str | None = None,
) -> str:
    payload = {
        "band": score.get("band"),
        "fragility": score.get("fragility"),
        "trigger": score.get("trigger"),
        "phase": score.get("phase"),
        "coverage": score.get("coverage"),
        "factors": score.get("factors"),
        "asof": score.get("asof"),
        "tier": tier,
        "edition": score.get("edition"),
        "edition_context": edition_context or score.get("edition_context"),
    }
    return json.dumps(payload, indent=2)


def _gemini_generate(api_key: str, prompt: str, system: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
    }
    r = httpx.post(url, params={"key": api_key}, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _translate_sections(api_key: str, en: dict[str, Any], lang_name: str) -> dict[str, Any]:
    payload = json.dumps({k: en.get(k, "") for k in _SECTION_KEYS if k != "markdown"}, ensure_ascii=False)
    system = TRANSLATE_SYSTEM.format(lang_name=lang_name)
    raw = _gemini_generate(api_key, payload, system)
    parsed = _parse_translation_json(raw, en)
    gated = _gate_translation(api_key, parsed, lang_name)
    return _lint_sections(gated)


def _parse_translation_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {k: data.get(k, fallback.get(k, "")) for k in _SECTION_KEYS if k != "markdown"}
    except json.JSONDecodeError:
        pass
    return {k: fallback.get(k, "") for k in _SECTION_KEYS if k != "markdown"}


def _gate_translation(api_key: str, translated: dict[str, Any], lang_name: str) -> dict[str, Any]:
    """Second pass: tone + no em-dash. Returns linted copy."""
    payload = json.dumps(translated, ensure_ascii=False)
    prompt = f"Language: {lang_name}\n\n{payload}"
    try:
        raw = _gemini_generate(api_key, prompt, GATE_SYSTEM)
        return _parse_translation_json(raw, translated)
    except Exception:
        return translated


def _fallback_translation(en: dict[str, Any], lang: str) -> dict[str, Any]:
    """Static fallback when no API key. Full-language stub, not mixed."""
    if lang == "zh":
        return {
            "headline": "AI板块进入警戒区间，杠杆信号抬头",
            "sub_headline": en.get("sub_headline", "").replace("Band:", "区间:"),
            "col1_html": "<p><strong>•</strong> 杠杆与估值因子处于偏热区间。</p><p><strong>•</strong> 覆盖率决定带宽宽度。</p>",
            "col2_html": "<p><strong>•</strong> 资本开支削减语言是主要触发观察项。</p>",
            "col3_html": "<p><strong>•</strong> 系统报告的是加载弹簧状态，不是崩盘日期。</p>",
            "caveat": "仅供决策支持，非投资建议。",
        }
    return {
        "headline": "Sektor AI memasuki zon waspada apabila isyarat leverage naik",
        "sub_headline": en.get("sub_headline", ""),
        "col1_html": "<p><strong>•</strong> Faktor leverage dan valuasi membaca zon panas.</p>",
        "col2_html": "<p><strong>•</strong> Grader capex-cut ialah pemantau pencetus utama.</p>",
        "col3_html": "<p><strong>•</strong> Sistem melaporkan spring dimuatkan, bukan tarikh ranap.</p>",
        "caveat": "Sokongan keputusan sahaja. Bukan nasihat pelaburan.",
    }


def _section_bullets(md: str, heading: str) -> list[str]:
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
    m = re.search(pattern, md, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    bullets = []
    for line in m.group(1).strip().splitlines():
        line = line.strip()
        if line.startswith(("-", "*")):
            bullets.append(line.lstrip("-* ").strip())
    return bullets[:3]


def _parse_sections(raw: str, score: dict[str, Any]) -> dict[str, Any]:
    raw = lint_no_em_dash(raw.strip())
    signal = _section_bullets(raw, "Signal")
    structure = _section_bullets(raw, "Structure")
    risk = _section_bullets(raw, "Risk")

    def _html(bullets: list[str]) -> str:
        if not bullets:
            return f"<p>{raw[:400]}</p>"
        return "".join(f"<p><strong>•</strong> {b}</p>" for b in bullets)

    band = score.get("band", "n/a")
    headline = signal[0] if signal else f"Market posture in {band} band"
    return {
        "headline": headline[:120],
        "sub_headline": f"Band: {band} · Phase: {score.get('phase', 'n/a')}",
        "col1_html": _html(signal),
        "col2_html": _html(structure),
        "col3_html": _html(risk),
        "caveat": "Decision-support only. Not investment advice.",
        "markdown": raw,
        "score": score,
    }


def _template_sections(score: dict[str, Any], tier: str) -> dict[str, Any]:
    band = score.get("band", "n/a")
    f = score.get("fragility", "n/a")
    t = score.get("trigger", "n/a")
    cov = score.get("coverage")
    cov_pct = f"{float(cov) * 100:.0f}%" if cov is not None else "n/a"
    return {
        "headline": f"AI sector enters {band} zone as leverage signals mount",
        "sub_headline": f"Fragility {f}, trigger {t} · band {band}",
        "col1_html": (
            f"<p>The system's <strong>Leverage (L)</strong> and <strong>Valuation (V)</strong> factors "
            f"read in the <strong>{band}</strong> band.</p>"
            f"<p>Coverage is <strong>{cov_pct}</strong>. Band width reflects missing data honestly.</p>"
        ),
        "col2_html": (
            "<p>The <strong>capex-cut NLP grader</strong> is the primary trigger watch. "
            "No formal hyperscaler capex cut has fired yet.</p>"
            + (
                "<p><strong>S, B, C factors</strong> available on this tier.</p>"
                if tier in ("report", "briefing", "agent")
                else "<p><strong>S, B, C</strong> locked. Subscribe at $4.99/mo.</p>"
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
