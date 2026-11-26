"""
briefing/crosscheck.py: a second opinion on market figures.

Yahoo is the primary quote source. Twice in live runs it produced a wrong one-day change (an
empty daily bar, a futures row on the wrong base), and it cannot serve some China indices at all.
So each table row may name a second, independent provider in config (`verify: "tencent:sh000001"`):

  Tencent Finance  qt.gtimg.cn    mainland China, Hong Kong and US indices and shares, with a timestamp
  Sina Finance     hq.sinajs.cn   Japan, Korea, Taiwan, Australia indices (only rows that carry a date:
                                  Sina's undated rows were measured to be stale by months)

reconcile() then decides, per row: confirmed, conflict (figure withheld from readers), or single.
Both APIs are keyless and return GBK text. Nothing here raises: a failure becomes a note in `problems`.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import httpx

_UA = {"User-Agent": "Mozilla/5.0 (compatible; newsreader/1.0)"}
_URLS = {"tencent": "https://qt.gtimg.cn/q=", "sina": "https://hq.sinajs.cn/list="}
_HEADERS = {"tencent": _UA, "sina": {**_UA, "Referer": "https://finance.sina.com.cn"}}
NAMES = {"tencent": "Tencent Finance", "sina": "Sina Finance"}
TOLERANCE = 0.25          # percentage points between two providers for the same closed session
LIVE_TOLERANCE = 1.0      # while a market is trading the two are sampled at different moments


@dataclass
class Reading:
    provider: str          # "tencent" | "sina"
    code: str
    price: float
    pct_1d: float
    session_date: str      # YYYY-MM-DD as the provider stamps it (exchange-local for Tencent)


def _num(text: str) -> float | None:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _date(stamp: str) -> str | None:
    """'20261120100927', '2026/11/20 09:54:27' or '2026-11-19 16:59:18' -> '2026-11-20'."""
    m = re.match(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", stamp or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def parse_tencent(text: str) -> dict[str, Reading]:
    """Full-format rows: v_sh000001="1~name~code~price~prev_close~open~...~[30]timestamp~[31]change~[32]pct~..."."""
    out: dict[str, Reading] = {}
    for code, body in re.findall(r'v_(\w+)="([^"]*)"', text or ""):
        f = body.split("~")
        if len(f) < 33:
            continue
        price, prev, pct, day = _num(f[3]), _num(f[4]), _num(f[32]), _date(f[30])
        if not (price and prev and price > 0 and prev > 0 and pct is not None and day):
            continue
        if abs((price / prev - 1) * 100 - pct) > 0.05:      # the row contradicts itself: do not trust it
            continue
        out[code] = Reading("tencent", code, price, pct, day)
    return out


def parse_sina(text: str) -> dict[str, Reading]:
    """Global-index rows: var hq_str_b_NKY="name,price,change,pct,time,time,[6]date,[7]time,open,[9]prev_close,...".
    A row without a date in field 6 is ignored: those were measured to be stale."""
    out: dict[str, Reading] = {}
    for code, body in re.findall(r'hq_str_(\w+)="([^"]*)"', text or ""):
        f = body.split(",")
        if len(f) < 10 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f[6].strip()):
            continue
        price, pct, prev = _num(f[1]), _num(f[3]), _num(f[9])
        if not (price and prev and price > 0 and prev > 0 and pct is not None):
            continue
        if abs((price / prev - 1) * 100 - pct) > 0.05:
            continue
        out[code] = Reading("sina", code, price, pct, f[6].strip())
    return out


_PARSERS = {"tencent": parse_tencent, "sina": parse_sina}


def fetch_readings(specs: list[str], problems: list[str] | None = None) -> dict[str, Reading]:
    """specs like "tencent:sh000001" -> {spec: Reading}. One request per provider."""
    problems = problems if problems is not None else []
    out: dict[str, Reading] = {}
    by_provider: dict[str, list[str]] = {}
    for spec in specs:
        provider, _, code = spec.partition(":")
        if provider in _URLS and re.fullmatch(r"\w+", code):
            by_provider.setdefault(provider, []).append(code)
        else:
            problems.append(f"second source '{spec}' is not a known provider code")
    for provider, codes in by_provider.items():
        try:
            r = httpx.get(_URLS[provider] + ",".join(codes), headers=_HEADERS[provider], timeout=15)
            r.raise_for_status()
            found = _PARSERS[provider](r.content.decode("gbk", "replace"))
        except Exception as exc:
            problems.append(f"second price source {NAMES[provider]} unavailable ({type(exc).__name__})")
            continue
        for code in codes:
            if code in found:
                out[f"{provider}:{code}"] = found[code]
    return out


def reconcile(pct: float | None, session_date: str, live: bool, reading: Reading | None) -> tuple[str, str]:
    """(status, note) for one table row.
      confirmed  same closed session, the two figures agree within TOLERANCE
      conflict   same session, they disagree: the caller withholds the figure
      newer      the second source has a later session than the primary: the caller should use it
      single     nothing usable to compare with (no reading, primary has no figure, or an older reading)
    """
    if reading is None or pct is None:
        return "single", ""
    if reading.session_date > session_date:
        return "newer", f"{NAMES[reading.provider]} has a later session"
    if reading.session_date < session_date:
        return "single", ""
    gap = abs(reading.pct_1d - pct)
    if gap > (LIVE_TOLERANCE if live else TOLERANCE):
        return "conflict", f"{NAMES[reading.provider]} shows {reading.pct_1d:+.1f}%"
    return ("single", "") if live else ("confirmed", "")
