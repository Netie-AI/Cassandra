"""
calendar_guard.py — the system only runs on days the market is open, and it always knows today's date
and year (holidays shift annually). Three intraday runs are defined relative to the Asia/US sessions.

Uses `exchange_calendars` if installed (handles every year's NYSE holidays); otherwise falls back to a
weekday + fixed US-holiday approximation. The fallback is good enough to avoid weekend/obvious-holiday
runs but you should `pip install exchange_calendars` for production accuracy.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

try:
    import exchange_calendars as xcals
    _NYSE = xcals.get_calendar("XNYS")
    _HAVE_XCALS = True
except Exception:                       # fallback
    _NYSE = None
    _HAVE_XCALS = False


class RunSlot(str, Enum):
    ASIA_PM = "asia_pm"     # 12:00 local — Korea/China/Asia sentiment settle
    PRE_OPEN = "pre_open"   # 21:00 local — prep before US open
    OVERNIGHT = "overnight" # 00:00 local — overnight wrap

# local (UTC+8) wall-clock for each slot
SLOT_TIME = {RunSlot.ASIA_PM: (12, 0), RunSlot.PRE_OPEN: (21, 0), RunSlot.OVERNIGHT: (0, 0)}


def _fallback_is_trading_day(d: dt.date) -> bool:
    if d.weekday() >= 5:                  # Sat/Sun
        return False
    # minimal fixed US market holidays (month, day) — extend as needed
    fixed = {(1, 1), (7, 4), (12, 25)}
    if (d.month, d.day) in fixed:
        return False
    return True


def is_trading_day(d: dt.date | None = None) -> bool:
    d = d or dt.date.today()
    if _HAVE_XCALS:
        return bool(_NYSE.is_session(d.isoformat()))
    return _fallback_is_trading_day(d)


def should_run(now: dt.datetime | None = None, tolerance_min: int = 20) -> RunSlot | None:
    """Return the RunSlot if `now` is within tolerance of a scheduled slot on a trading day, else None.

    Note: news runs are useful even on a US holiday if Asia is open, but to keep it simple we gate on
    the NYSE session. Relax this if you want Asia-session-only runs.
    """
    now = now or dt.datetime.now()
    if not is_trading_day(now.date()):
        return None
    for slot, (hh, mm) in SLOT_TIME.items():
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if abs((now - target).total_seconds()) <= tolerance_min * 60:
            return slot
    return None


def next_trading_day(d: dt.date | None = None) -> dt.date:
    d = (d or dt.date.today()) + dt.timedelta(days=1)
    while not is_trading_day(d):
        d += dt.timedelta(days=1)
    return d


def recent_window(days: int = 5, end: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """A 'pull only recent news' window: from `days` trading days back to today."""
    end = end or dt.date.today()
    start = end
    counted = 0
    while counted < days:
        start -= dt.timedelta(days=1)
        if is_trading_day(start):
            counted += 1
    return start, end


if __name__ == "__main__":
    today = dt.date.today()
    print(f"backend: {'exchange_calendars' if _HAVE_XCALS else 'fallback'}  | today={today} ({today.strftime('%A')})")
    print(f"is_trading_day(today) = {is_trading_day(today)}")
    print(f"next_trading_day      = {next_trading_day(today)}")
    print(f"recent 5-session window = {recent_window(5)}")
    print(f"should_run(noon)      = {should_run(dt.datetime.combine(today, dt.time(12, 5)))}")
