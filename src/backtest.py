"""Backtest replay stub — descriptive analog match only, not predictive."""
from __future__ import annotations

from pydantic import BaseModel, Field

from . import store


class BacktestResult(BaseModel):
    start_date: str
    end_date: str
    crs_series: list[dict]
    analog_match: str | None = None
    timing_label: str = "12-18 months to capitulation (historical median)"
    disclaimer: str = Field(
        default="Descriptive only. Not predictive. Past regimes do not determine future timing."
    )


def run_backtest(start: str, end: str) -> BacktestResult:
    """Load historical CRS from store; cosine analog match when history available."""
    from .analog import cosine_match

    scores = store.get_score_history(start, end)
    analog_match = None
    if scores:
        last = scores[-1]
        key, _sim = cosine_match(last["crs"], last["f"], last["t"])
        analog_match = key
    return BacktestResult(
        start_date=start,
        end_date=end,
        crs_series=scores,
        analog_match=analog_match,
        timing_label="12-18 months to capitulation (historical median)",
        disclaimer="Descriptive only. Not predictive. Past regimes do not determine future timing.",
    )
