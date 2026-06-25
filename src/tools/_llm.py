"""
_llm.py — shared OpenRouter JSON extraction for subagents.

Design (ponytail + 2025 best practice, no LangChain):
  - Pre-summarize in Python; LLM extracts structured fields only
  - JSON-only output, temperature 0, schema in system prompt
  - No chain-of-thought in responses (auditability + token cost)
  - Fail-safe merge with caller-supplied fallback dict
  - LLM never computes CRS — only maps pre-fetched data to schema keys
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from ._env import load_env

load_env()

# Shared prefix — appended to every subagent system prompt
SUBAGENT_BASE = """\
You are a read-only market intelligence extractor.
Return ONLY one JSON object matching the schema. No markdown. No prose outside JSON.
Never compute CRS, bands, trades, or position sizes.
If a field is unknown from the input: null. Never invent numbers.
Be precise: extract values exactly as stated in the input when present.
"""

DEFAULT_MAX_TOKENS = 300
DEFAULT_TIMEOUT = 45
MAX_USER_CHARS = 4000


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return text


def _parse_json_object(text: str) -> dict[str, Any]:
    text = _strip_fences(text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


def _merge_schema(fallback: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """Keep fallback keys; overlay parsed values for known keys only."""
    out = dict(fallback)
    for key in fallback:
        if key in parsed:
            out[key] = parsed[key]
    return out


def summarize_metrics(metrics: list) -> list[dict[str, Any]]:
    """Compact MetricReading list for LLM user payload."""
    rows = []
    for m in metrics:
        rows.append({
            "name": m.name,
            "factor": m.factor,
            "raw_value": m.raw_value,
            "source": m.source,
            "note": m.note,
        })
    return rows


def llm_extract(
    system: str,
    user_content: str,
    fallback: dict[str, Any],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_user_chars: int = MAX_USER_CHARS,
) -> dict[str, Any]:
    """
    Single OpenRouter call → parsed JSON merged with fallback.
    Without OPENROUTER_API_KEY returns fallback unchanged (tool-bridge mode).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return dict(fallback)

    model = os.getenv("OPENROUTER_SUBAGENT_MODEL", "anthropic/claude-sonnet-4-6")
    user = user_content[:max_user_chars]
    full_system = f"{SUBAGENT_BASE}\n\n{system.strip()}"

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user},
        ],
    }
    # OpenAI-compatible JSON mode (supported by many OpenRouter models)
    body["response_format"] = {"type": "json_object"}

    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        parsed = _parse_json_object(text)
        return _merge_schema(fallback, parsed)
    except Exception:
        return dict(fallback)
