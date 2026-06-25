"""Helpers to map LLM extracts + tool metrics into MetricReading rows."""
from __future__ import annotations

import datetime as dt
from typing import Any

from ..schemas import Direction, MetricReading


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def metric(
    name: str,
    factor: str,
    raw: float | int | None,
    source: str,
    *,
    direction: Direction = Direction.BEARISH_HIGH,
    note: str | None = None,
    use_percentile: bool = False,
) -> MetricReading:
    val = float(raw) if raw is not None else None
    return MetricReading(
        name=name,
        factor=factor,
        raw_value=val,
        direction=direction,
        source=source,
        asof=_now(),
        use_percentile=use_percentile,
        note=note,
    )


def merge_metric(
    metrics: list[MetricReading],
    name: str,
    factor: str,
    raw: float | int | None,
    source: str,
    **kwargs: Any,
) -> list[MetricReading]:
    """Replace same-named metric or append."""
    out = [m for m in metrics if m.name != name]
    if raw is not None:
        out.append(metric(name, factor, raw, source, **kwargs))
    return out
