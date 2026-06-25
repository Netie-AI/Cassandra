"""
src/tools/fmp.py — Financial Modeling Prep: insider transactions, 13F, earnings transcripts

APIs used:
  /v4/insider-trading         → Form 4 insider buys/sells (Whale factor)
  /v3/institutional-holder    → 13F institutional positions (Whale factor)
  /v3/earning_call_transcript → earnings transcripts for capex-cut NLP (Trigger factor C)
  /v3/income-statement        → revenue for capex/revenue gap slope (Trigger factor C)

MetricReadings produced:
  insider_sell_buy_ratio  — factor S/Whale: high = insiders distributing
  capex_rev_gap_slope     — factor C: widening gap = more bearish
  cohort_fwd_ps           — factor V: forward price/sales of basket (if FMP provides estimates)

Transcripts are returned as raw text for the News Digestor's NLP grader — they are NOT read by LLM
here; heavy payload is handled in the orchestrator before the LLM sees it.

Run standalone: python -m src.tools.fmp
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import httpx

from ..schemas import Direction, MetricReading

_BASE = "https://financialmodelingprep.com/api"


def _key() -> str:
    k = os.environ.get("FMP_API_KEY", "")
    if not k:
        raise EnvironmentError("FMP_API_KEY not set")
    return k


def _get(path: str, params: dict | None = None) -> Optional[dict | list]:
    try:
        r = httpx.get(f"{_BASE}{path}",
                      params={"apikey": _key(), **(params or {})},
                      timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Insider transactions → sell/buy ratio
# --------------------------------------------------------------------------- #
def fetch_insider_metrics(basket: list[str], lookback_days: int = 90) -> list[MetricReading]:
    now = dt.datetime.utcnow()
    since = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()
    total_buy = total_sell = 0.0

    for ticker in basket[:15]:
        data = _get("/v4/insider-trading", {"symbol": ticker, "page": 0})
        if not data:
            continue
        txns = data if isinstance(data, list) else []
        for t in txns:
            date_str = t.get("transactionDate", "")
            if date_str < since:
                continue
            val = abs(float(t.get("value", 0) or 0))
            ttype = str(t.get("transactionType", "")).lower()
            if "sale" in ttype or "sell" in ttype or "s-" in ttype:
                total_sell += val
            elif "purchase" in ttype or "buy" in ttype or "p" == ttype.strip():
                total_buy += val

    ratio = total_sell / total_buy if total_buy > 0 else None
    return [MetricReading(
        name="insider_sell_buy_ratio", factor="S", raw_value=ratio,
        direction=Direction.BEARISH_HIGH,
        source=f"FMP:insider-trading:{','.join(basket[:5])}",
        asof=now,
        note=f"sell=${total_sell/1e6:.1f}M buy=${total_buy/1e6:.1f}M ratio={ratio:.2f}"
             if ratio else f"buy=${total_buy/1e6:.1f}M (no sells or no data)"
    )]


# --------------------------------------------------------------------------- #
# Capex / revenue gap slope — is the mismatch widening?
# --------------------------------------------------------------------------- #
def fetch_capex_rev_gap(hyperscalers: list[str]) -> list[MetricReading]:
    """
    For each hyperscaler: pull last 4 quarters of capex + revenue from income/cashflow statements.
    Compute gap = capex - revenue, then OLS slope of the gap over time.
    Positive slope = gap widening = more bearish.
    """
    now = dt.datetime.utcnow()
    gap_series: list[float] = []

    for ticker in hyperscalers:
        cf = _get(f"/v3/cash-flow-statement/{ticker}", {"period": "quarter", "limit": 8})
        inc = _get(f"/v3/income-statement/{ticker}", {"period": "quarter", "limit": 8})
        if not cf or not inc:
            continue
        cf_list = cf if isinstance(cf, list) else cf.get("financials", [])
        inc_list = inc if isinstance(inc, list) else inc.get("financials", [])
        for cf_q, inc_q in zip(cf_list[:4], inc_list[:4]):
            try:
                capex = abs(float(cf_q.get("capitalExpenditure", 0) or 0))
                rev = float(inc_q.get("revenue", 0) or 0)
                if rev > 0:
                    gap_series.append(capex - rev)
            except (TypeError, ValueError):
                continue

    if len(gap_series) < 3:
        return [MetricReading(name="capex_rev_gap_slope", factor="C", raw_value=None,
                              direction=Direction.BEARISH_HIGH, source="FMP:income+cashflow",
                              asof=now, note="insufficient data for slope")]

    import numpy as np
    x = np.arange(len(gap_series), dtype=float)
    slope = float(np.polyfit(x, gap_series, 1)[0])
    return [MetricReading(
        name="capex_rev_gap_slope", factor="C", raw_value=slope,
        direction=Direction.BEARISH_HIGH,
        source=f"FMP:cashflow+income:{','.join(hyperscalers)}",
        asof=now,
        note=f"slope={slope/1e9:.2f}B/qtr; +ve=widening gap"
    )]


# --------------------------------------------------------------------------- #
# Earnings transcripts (for News Digestor NLP — returned as raw text dict, NOT fed to LLM here)
# --------------------------------------------------------------------------- #
def fetch_transcripts(tickers: list[str], quarters_back: int = 2) -> dict[str, list[str]]:
    """
    Returns {ticker: [transcript_text, ...]} for the last `quarters_back` earnings calls.
    The News Digestor feeds these through the capex-cut NLP grader (not the LLM raw).
    Texts are paraphrased by the orchestrator before any LLM call.
    """
    year = dt.date.today().year
    out: dict[str, list[str]] = {}
    for ticker in tickers:
        texts = []
        for quarter in range(1, 5):   # try all quarters this year
            data = _get(f"/v3/earning_call_transcript/{ticker}",
                        {"year": year, "quarter": quarter})
            if data and isinstance(data, list) and data:
                texts.append(data[0].get("content", ""))
            if len(texts) >= quarters_back:
                break
        out[ticker] = [t for t in texts if t]
    return out


def fetch_all_whale(basket: list[str]) -> list[MetricReading]:
    out = []
    out.extend(fetch_insider_metrics(basket))
    hyperscalers = [t for t in basket if t in ("MSFT", "GOOGL", "AMZN", "META", "ORCL")]
    out.extend(fetch_capex_rev_gap(hyperscalers or basket[:5]))
    return out


if __name__ == "__main__":
    BASKET = ["NVDA", "MSFT", "GOOGL", "META", "MU"]
    try:
        metrics = fetch_all_whale(BASKET)
        for m in metrics:
            val = f"{m.raw_value:.4f}" if m.raw_value is not None else "MISSING"
            print(f"  {m.name:28s} {val:15s} | {m.note}")
        print("\ntranscripts (titles only):")
        txts = fetch_transcripts(["MSFT"], quarters_back=1)
        for k, v in txts.items():
            print(f"  {k}: {len(v)} transcript(s), first {min(200, len(v[0]) if v else 0)} chars:")
            if v:
                print(f"    {v[0][:200]}...")
    except EnvironmentError as e:
        print(f"  {e} — set FMP_API_KEY in .env")
