"""Market snapshot for homepage widgets — demo fallback when live feeds unavailable."""
from __future__ import annotations

import random
from datetime import datetime, timezone

import httpx

_VOL_1D = [
    {"sym": "MU", "pct": 8.6}, {"sym": "WDC", "pct": 7.2}, {"sym": "SMCI", "pct": -12.4},
    {"sym": "ARM", "pct": 8.2}, {"sym": "MSTR", "pct": -6.1}, {"sym": "AVGO", "pct": 5.8},
    {"sym": "AMD", "pct": -4.3}, {"sym": "CRWD", "pct": 3.1}, {"sym": "NVDA", "pct": 2.4},
    {"sym": "KLAC", "pct": -2.8}, {"sym": "AMAT", "pct": -1.9},
]
_VOL_5D = [
    {"sym": "ARM", "pct": 14.2}, {"sym": "SMCI", "pct": -11.8}, {"sym": "MSTR", "pct": -9.4},
    {"sym": "AVGO", "pct": 8.1}, {"sym": "NVDA", "pct": 6.2}, {"sym": "AMD", "pct": -5.4},
    {"sym": "CRWD", "pct": 4.8}, {"sym": "KLAC", "pct": -3.9}, {"sym": "AMAT", "pct": -3.1},
    {"sym": "TSM", "pct": 2.4}, {"sym": "MU", "pct": 3.8},
]
_VOL_1M = [
    {"sym": "ARM", "pct": 28.4}, {"sym": "MSTR", "pct": -22.1}, {"sym": "SMCI", "pct": -19.8},
    {"sym": "AVGO", "pct": 18.6}, {"sym": "CRWD", "pct": 15.2}, {"sym": "NVDA", "pct": 12.4},
    {"sym": "AMD", "pct": -10.1}, {"sym": "KLAC", "pct": -8.4}, {"sym": "TSM", "pct": 7.2},
    {"sym": "AMAT", "pct": -6.8}, {"sym": "MU", "pct": 9.1},
]

_INDICES = [
    {"sym": "SPX", "val": "5,634", "pct": -0.42},
    {"sym": "NDX", "val": "19,847", "pct": -0.61},
    {"sym": "VIX", "val": "18.24", "pct": 5.20},
    {"sym": "SOX", "val": "4,312", "pct": -1.18},
]

_TF_MAP = {"1D": _VOL_1D, "5D": _VOL_5D, "1M": _VOL_1M}
_SCALE = {"1D": 14.0, "5D": 16.0, "1M": 30.0}


def _spark_seed(sym: str, n: int = 20) -> list[float]:
    rng = random.Random(hash(sym) & 0xFFFF)
    v = 50.0
    out = []
    for _ in range(n):
        v += rng.uniform(-1.2, 1.2)
        out.append(v)
    return out


def top_movers(tf: str = "1D", sector: str = "tech,semis", limit: int = 10) -> dict:
    tf = tf.upper() if tf.upper() in _TF_MAP else "1D"
    limit = max(1, min(limit, 20))
    rows = sorted(_TF_MAP[tf], key=lambda r: abs(r["pct"]), reverse=True)[:limit]
    return {"tf": tf, "sector": sector, "scale": _SCALE[tf], "movers": rows}


def index_snapshot() -> dict:
    rows = []
    for r in _INDICES:
        up = r["pct"] >= 0
        rows.append({**r, "spark": _spark_seed(r["sym"]), "color": "#15803D" if up else "#B91C1C"})
    return {"indices": rows}


_FNG_URL = "https://api.alternative.me/fng/"


def _fng_label_color(value: int) -> tuple[str, str]:
    if value < 45:
        return "Fear", "#B91C1C"
    if value > 55:
        return "Greed", "#15803D"
    return "Neutral", "#92400E"


def _fetch_alternative_me_fng() -> dict | None:
    """Alternative.me crypto Fear & Greed — no key, used as sentiment proxy."""
    try:
        r = httpx.get(_FNG_URL, params={"limit": 28}, timeout=8)
        r.raise_for_status()
        data = r.json().get("data") or []
        if not data:
            return None
        latest = data[0]
        value = int(latest["value"])
        label, color = _fng_label_color(value)
        spark = [float(d["value"]) for d in reversed(data)]
        ts = latest.get("timestamp")
        asof = (
            datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            if ts
            else datetime.now(timezone.utc).date().isoformat()
        )
        return {
            "value": value,
            "label": label,
            "color": color,
            "source": "alternative.me:fng",
            "asof": asof,
            "note": "Crypto Fear & Greed proxy until CNN equity index is wired.",
            "spark": spark,
        }
    except Exception:
        return None


def _demo_fear_greed() -> dict:
    value = 42
    label, color = _fng_label_color(value)
    return {
        "value": value,
        "label": label,
        "color": color,
        "source": "demo_proxy",
        "asof": datetime.now(timezone.utc).date().isoformat(),
        "note": "Demo fallback — live F&G unavailable.",
        "spark": _spark_seed("fear_greed", 28),
    }


def fear_greed() -> dict:
    """Fear & Greed: alternative.me when reachable, else hardcoded demo."""
    return _fetch_alternative_me_fng() or _demo_fear_greed()
