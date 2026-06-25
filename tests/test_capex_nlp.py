"""Capex NLP grader unit tests + optional live calibration."""
from __future__ import annotations

import os

import pytest

from src.tools.capex_nlp import (
    CAPEX_CUT_CALIBRATION,
    GRADER_SYSTEM,
    _parse_score,
    score_capex_cut,
)


def test_grader_system_has_tiebreaker():
    assert "flexibility" in GRADER_SYSTEM.lower()
    assert "0.55" in GRADER_SYSTEM


def test_parse_score_json():
    score, reason = _parse_score('{"score": 0.71, "band": "CONCERN", "reason": "pace moderation"}')
    assert score == 0.71
    assert "moderation" in reason


def test_parse_score_fenced():
    score, _ = _parse_score("```json\n{\"score\": 0.93}\n```")
    assert score == 0.93


def test_empty_snippet_returns_zero():
    score, reason = score_capex_cut("")
    assert score == 0.0
    assert "empty" in reason


def test_calibration_set_structure():
    assert len(CAPEX_CUT_CALIBRATION) == 10
    ids = {x["id"] for x in CAPEX_CUT_CALIBRATION}
    assert ids == {f"cc_{i:02d}" for i in range(1, 11)}


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"),
    reason="no LLM key for live calibration",
)
@pytest.mark.parametrize("case", CAPEX_CUT_CALIBRATION, ids=lambda c: c["id"])
def test_calibration_live_within_tolerance(case):
    score, _ = score_capex_cut(case["snippet"])
    assert abs(score - case["expected_score"]) <= 0.08, (
        f"{case['id']}: got {score}, expected {case['expected_score']}"
    )
