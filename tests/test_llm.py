"""Shared LLM extract utility tests."""
from __future__ import annotations

from src.tools._llm import _merge_schema, _parse_json_object, llm_extract


def test_parse_json_object_with_fences():
    data = _parse_json_object('```json\n{"supply_tell": 0.4}\n```')
    assert data["supply_tell"] == 0.4


def test_merge_schema_keeps_fallback_keys():
    fb = {"a": None, "b": 1}
    merged = _merge_schema(fb, {"a": 0.5, "c": 99})
    assert merged == {"a": 0.5, "b": 1}


def test_llm_extract_no_key_returns_fallback():
    out = llm_extract("sys", "user", {"x": None, "y": 1})
    assert out == {"x": None, "y": 1}
