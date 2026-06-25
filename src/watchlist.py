"""Per-user watchlist persistence (SQLite). Default: LEU + mega-cap semis."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .store import _conn

DEFAULT_TICKERS = ["LEU", "NVDA", "MSFT", "AMZN", "TSM"]

# Demo quotes — replace with live feed when market data client is wired.
_DEMO_QUOTES: dict[str, dict] = {
    "LEU": {"px": "80.14", "pct": 3.21},
    "NVDA": {"px": "118.42", "pct": 2.41},
    "MSFT": {"px": "438.71", "pct": 0.94},
    "AMZN": {"px": "214.08", "pct": -0.38},
    "TSM": {"px": "191.55", "pct": 1.12},
    "MU": {"px": "94.18", "pct": 2.04},
    "AMD": {"px": "128.40", "pct": -2.34},
    "AVGO": {"px": "168.20", "pct": 1.55},
}


def _ensure_table() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                user_id TEXT PRIMARY KEY,
                tickers_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def get_watchlist(user_id: str = "local") -> dict:
    _ensure_table()
    uid = (user_id or "local").strip()[:64] or "local"
    with _conn() as c:
        db_row = c.execute(
            "SELECT tickers_json, updated_at FROM watchlists WHERE user_id = ?",
            (uid,),
        ).fetchone()
    if db_row:
        tickers = json.loads(db_row["tickers_json"])
    else:
        tickers = list(DEFAULT_TICKERS)
    live: dict[str, dict] = {}
    try:
        from .tools.yfinance_client import fetch_quotes
        live = fetch_quotes(tickers)
    except Exception:
        live = {}

    rows = []
    for sym in tickers:
        s = sym.upper()
        q = live.get(s) or _DEMO_QUOTES.get(s, {"px": "—", "pct": 0.0})
        row = {"sym": s, "px": q["px"], "pct": q["pct"]}
        if q.get("source"):
            row["source"] = q["source"]
        if q.get("asof"):
            row["asof"] = q["asof"]
        rows.append(row)
    return {
        "user_id": uid,
        "tickers": tickers,
        "rows": rows,
        "updated_at": db_row["updated_at"] if db_row else None,
    }


def update_watchlist(user_id: str, tickers: list[str]) -> dict:
    _ensure_table()
    uid = (user_id or "local").strip()[:64] or "local"
    cleaned = []
    seen: set[str] = set()
    for t in tickers:
        s = str(t).strip().upper()
        if not s or not s.isalpha() or len(s) > 6:
            continue
        if s in seen:
            continue
        seen.add(s)
        cleaned.append(s)
    if not cleaned:
        cleaned = list(DEFAULT_TICKERS)
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO watchlists (user_id, tickers_json, updated_at) VALUES (?,?,?)",
            (uid, json.dumps(cleaned), now),
        )
    return get_watchlist(uid)
