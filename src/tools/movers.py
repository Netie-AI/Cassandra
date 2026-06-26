"""Live watchlist movers via Finnhub — gates on NYSE market status."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from ..schemas import MoverRead
from ._env import get_key, load_env

load_env()
_LOG = logging.getLogger(__name__)
_BASE = "https://finnhub.io/api/v1"
_WATCHLIST = ("LEU", "NOW", "BABA", "MU", "TSM")
_SKIP_SYMBOLS = frozenset({"SPACEX", "SPACE"})


def _get(path: str, params: dict | None = None) -> dict | list | None:
    key = get_key("FINNHUB_API_KEY")
    if not key:
        return None
    try:
        r = httpx.get(
            f"{_BASE}{path}",
            params={"token": key, **(params or {})},
            timeout=12,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _LOG.debug("Finnhub %s failed: %s", path, exc)
        return None


def nyse_is_open() -> bool | None:
    """True when US equity session is open; None if status unavailable."""
    data = _get("/stock/market-status", {"exchange": "US"})
    if not isinstance(data, dict):
        return None
    return bool(data.get("isOpen"))


def _quote(symbol: str) -> MoverRead | None:
    if symbol.upper() in _SKIP_SYMBOLS:
        _LOG.info("Skipping non-listed symbol %s", symbol)
        return None
    data = _get("/quote", {"symbol": symbol.upper()})
    if not isinstance(data, dict):
        return None
    price = data.get("c")
    pct = data.get("dp")
    if price is None and pct is None:
        return None
    pct_f = float(pct) if pct is not None else None
    if pct_f is not None and abs(pct_f) > 12.0:
        _LOG.warning(
            "MOVERS_OUTLIER symbol=%s pct=%.2f — verify against yfinance",
            symbol.upper(),
            pct_f,
        )
    return MoverRead(
        symbol=symbol.upper(),
        price=float(price) if price is not None else None,
        pct_change=pct_f,
        source="finnhub",
    )


def fetch_watchlist_movers(*, symbols: tuple[str, ...] = _WATCHLIST) -> list[MoverRead]:
    """
    Pull live quotes for the desk watchlist.
    Returns empty list when FINNHUB_API_KEY is absent (coverage unaffected).
    """
    if not get_key("FINNHUB_API_KEY"):
        return []

    open_status = nyse_is_open()
    if open_status is False:
        _LOG.info("NYSE closed — skipping live mover quotes")
        return []

    out: list[MoverRead] = []
    for sym in symbols:
        if sym.upper() in _SKIP_SYMBOLS:
            _LOG.info("Skipping non-listed symbol %s", sym)
            continue
        row = _quote(sym)
        if row:
            out.append(row)
    out.sort(key=lambda m: abs(m.pct_change or 0.0), reverse=True)
    return out


if __name__ == "__main__":
    movers = fetch_watchlist_movers()
    print(f"movers={len(movers)} asof={datetime.now(timezone.utc).isoformat()}")
    for m in movers:
        print(f"  {m.symbol}: {m.price} ({m.pct_change:+.2f}%)" if m.pct_change is not None else f"  {m.symbol}: {m.price}")
