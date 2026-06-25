"""Build-time copy lint: reject em/en dashes in user-facing generated text."""
from __future__ import annotations

import re

EM_DASH_RE = re.compile(r"[\u2014\u2013]")


def has_em_dash(text: str) -> bool:
    return bool(text and EM_DASH_RE.search(text))


def lint_no_em_dash(text: str) -> str:
    """Replace em/en dashes with comma breaks. Mechanical, not prompt-based."""
    if not text:
        return text
    out = re.sub(r"\s*[\u2014\u2013]\s*", ", ", text)
    out = re.sub(r",\s+,", ", ", out)
    return out


def lint_dict_strings(data: dict, keys: tuple[str, ...] | None = None) -> dict:
    keys = keys or tuple(data.keys())
    for key in keys:
        val = data.get(key)
        if isinstance(val, str):
            data[key] = lint_no_em_dash(val)
    return data


def assert_no_em_dash(text: str, context: str = "") -> None:
    if has_em_dash(text):
        raise ValueError(f"Em-dash found in {context or 'copy'}")
