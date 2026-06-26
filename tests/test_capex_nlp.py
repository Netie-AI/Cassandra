"""Capex NLP grader unit tests + optional live calibration."""
from __future__ import annotations

import os

import pytest

from src.tools.capex_nlp import (
    CAPEX_CUT_CALIBRATION,
    GRADER_SYSTEM,
    RUBRIC,
    _parse_score,
    score_capex_cut,
)


def test_rubric_has_edge_cases():
    assert "Past-tense cuts" in RUBRIC
    assert "Retail/logistics capex" in RUBRIC
    assert "0.60" in RUBRIC


def test_grader_system_matches_rubric():
    assert GRADER_SYSTEM is RUBRIC


def test_parse_score_json():
    score = _parse_score('{"score": 0.71, "reason": "pace moderation"}')
    assert score == 0.71


def test_parse_score_fenced():
    score = _parse_score("```json\n{\"score\": 0.93}\n```")
    assert score == 0.93


def test_parse_failure_default():
    assert _parse_score("not json") == 0.5


def test_empty_snippet_returns_zero():
    assert score_capex_cut("") == 0.0


def test_calibration_set_structure():
    assert len(CAPEX_CUT_CALIBRATION) == 10
    ids = {x["id"] for x in CAPEX_CUT_CALIBRATION}
    assert ids == {f"cc_{i:02d}" for i in range(1, 11)}
    for ex in CAPEX_CUT_CALIBRATION:
        assert "source" in ex
        assert "reasoning" in ex


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"),
    reason="no LLM key for live calibration",
)
@pytest.mark.parametrize("case", CAPEX_CUT_CALIBRATION, ids=lambda c: c["id"])
def test_calibration_live_within_tolerance(case):
    score = score_capex_cut(case["snippet"])
    assert abs(score - case["expected_score"]) <= 0.08, (
        f"{case['id']}: got {score}, expected {case['expected_score']}"
    )
