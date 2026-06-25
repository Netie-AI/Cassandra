"""
src/tools/finra.py — FINRA margin statistics (monthly)

FINRA publishes aggregate margin debt monthly with ~1-month lag.
Source: https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics

MetricReadings produced (factor L — Leverage):
  margin_debt_raw      — absolute debit balance $M (directional context only)
  margin_debt_yoy      — YoY % change (+1 higher=more bearish)
  margin_to_mktcap     — margin_debt / S&P 500 mktcap proxy (+1)
  negative_credit_bal  — debit_balance - free_credit_balance (+1)

Freshness: monthly. The scorer's freshness penalty decays this over the month.
Run standalone: python -m src.tools.finra
"""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading

# FINRA margin statistics page (HTML contains the data table)
_PAGE_URL = "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics"
# Fallback: direct CSV path FINRA has published (path changes; page scrape is the primary)
_CSV_FALLBACK = "https://www.finra.org/sites/default/files/2024-10/margin-statistics.csv"

# Approximate S&P 500 total market cap proxy (updated in config; $M)
# Production: pull from FRED WILL5000PRFC / GDP instead
_SP500_MKTCAP_M_APPROX = 55_000_000.0


def _parse_html_table(html: str) -> list[dict]:
    """Extract rows from the FINRA margin statistics HTML table.
    Returns list of {date: str, debit: float, free_credit: float} newest-first."""
    rows = []
    # FINRA table has headers: End of Month | Debit Balances | Free Credit Balances | ...
    # Pattern: capture month-year + two dollar values
    pattern = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})"
        r"(?:[^$]*)\$\s*([\d,]+)"   # debit balance
        r"(?:[^$]*)\$\s*([\d,]+)",  # free credit
        re.IGNORECASE
    )
    for m in pattern.finditer(html):
        month_str, year, debit_str, credit_str = m.groups()
        try:
            month = dt.datetime.strptime(month_str, "%B").month
            year = int(year)
            debit = float(debit_str.replace(",", ""))
            credit = float(credit_str.replace(",", ""))
            rows.append({
                "date": dt.date(year, month, 1),
                "debit_m": debit,
                "free_credit_m": credit,
            })
        except (ValueError, OverflowError):
            continue
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def _fetch_rows() -> list[dict]:
    """Attempt to pull the FINRA margin table. Try HTML first, CSV fallback, empty on failure."""
    headers = {"User-Agent": "CassandraResearchBot/1.0 (market research; no commercial use)"}
    try:
        r = httpx.get(_PAGE_URL, headers=headers, timeout=30, follow_redirects=True)
        r.raise_for_status()
        rows = _parse_html_table(r.text)
        if rows:
            return rows
    except Exception:
        pass
    # CSV fallback
    try:
        r = httpx.get(_CSV_FALLBACK, headers=headers, timeout=30, follow_redirects=True)
        r.raise_for_status()
        rows = _parse_csv(r.text)
        if rows:
            return rows
    except Exception:
        pass
    return []


def _parse_csv(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            d = dt.datetime.strptime(parts[0].strip(), "%m/%Y").date().replace(day=1)
            debit = float(parts[1].strip().replace("$", "").replace(",", ""))
            credit = float(parts[2].strip().replace("$", "").replace(",", ""))
            rows.append({"date": d, "debit_m": debit, "free_credit_m": credit})
        except (ValueError, IndexError):
            continue
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def _yoy(rows: list[dict], key: str) -> Optional[float]:
    """Compute YoY % change between the most-recent and the reading ~12 months prior."""
    if len(rows) < 13:
        return None
    latest = rows[0][key]
    prior = rows[12][key]      # ~12 months back
    if prior == 0:
        return None
    return (latest - prior) / prior * 100.0


def fetch(sp500_mktcap_m: float = _SP500_MKTCAP_M_APPROX) -> list[MetricReading]:
    rows = _fetch_rows()
    now = dt.datetime.utcnow()

    if not rows:
        note = "FINRA margin page unavailable — check URL or network"
        return [
            MetricReading(name="margin_debt_yoy", factor="L", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="FINRA", asof=now, note=note),
            MetricReading(name="margin_to_mktcap", factor="L", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="FINRA", asof=now, note=note),
            MetricReading(name="negative_credit_bal", factor="L", raw_value=None,
                          direction=Direction.BEARISH_HIGH, source="FINRA", asof=now, note=note),
        ]

    latest = rows[0]
    asof = dt.datetime(latest["date"].year, latest["date"].month, 1)
    debit_m = latest["debit_m"]
    credit_m = latest["free_credit_m"]
    yoy = _yoy(rows, "debit_m")
    neg_credit = debit_m - credit_m
    m_to_mc = debit_m / sp500_mktcap_m if sp500_mktcap_m else None

    return [
        MetricReading(
            name="margin_debt_yoy", factor="L", raw_value=yoy,
            direction=Direction.BEARISH_HIGH, source=f"FINRA:{_PAGE_URL}",
            asof=asof, note=f"latest={debit_m:,.0f}M YoY={yoy:.1f}%" if yoy else "insufficient history for YoY"
        ),
        MetricReading(
            name="margin_to_mktcap", factor="L", raw_value=m_to_mc,
            direction=Direction.BEARISH_HIGH, source=f"FINRA:{_PAGE_URL}",
            asof=asof, note=f"debt {debit_m:,.0f}M / mktcap {sp500_mktcap_m:,.0f}M"
        ),
        MetricReading(
            name="negative_credit_bal", factor="L", raw_value=neg_credit,
            direction=Direction.BEARISH_HIGH, source=f"FINRA:{_PAGE_URL}",
            asof=asof, note=f"debit-free_credit={neg_credit:,.0f}M"
        ),
    ]


if __name__ == "__main__":
    readings = fetch()
    for r in readings:
        status = f"raw={r.raw_value:.2f}" if r.raw_value is not None else "MISSING"
        print(f"  {r.name:30s} {status:20s} factor={r.factor} asof={r.asof.date()} | {r.note}")
