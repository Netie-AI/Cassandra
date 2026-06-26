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
    from .analog import CORPUS, cosine_match

    scores = store.get_score_history(start, end)
    analog_match = None
    if scores:
        last = scores[-1]
        key, _sim = cosine_match(last["crs"], last["f"], last["t"])
        analog_match = key
    if analog_match is None:
        timing_label = "No strong historical analog at current readings"
    else:
        months = CORPUS[analog_match]["months_to_capitulation"]
        timing_label = (
            f"Historical analog suggests {months}–{months + 6} months to capitulation "
            "(one prior case)"
        )
    return BacktestResult(
        start_date=start,
        end_date=end,
        crs_series=scores,
        analog_match=analog_match,
        timing_label=timing_label,
        disclaimer="Descriptive only. Not predictive. Past regimes do not determine future timing.",
    )
