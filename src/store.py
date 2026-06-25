"""SQLite persistence for DailyScore + metric history."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "store" / "scores.sqlite"


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS daily_scores (
            asof TEXT PRIMARY KEY,
            crs REAL, band TEXT, band_halfwidth REAL, confidence REAL,
            fragility REAL, trigger REAL, coverage REAL,
            factors_json TEXT, momentum_state TEXT, df_dt REAL,
            phase TEXT, phase_confidence REAL, payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS metric_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asof TEXT, name TEXT, factor TEXT, raw_value REAL,
            source TEXT, note TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_metric_name ON metric_history(name, asof);
    """)
    return c


def save_score(score, extra: dict | None = None) -> None:
    from .schemas import DailyScore
    assert isinstance(score, DailyScore)
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO daily_scores
            (asof, crs, band, band_halfwidth, confidence, fragility, trigger, coverage,
             factors_json, momentum_state, df_dt, phase, phase_confidence, payload_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            score.asof.isoformat(), score.crs, score.band_label, score.band_halfwidth,
            score.confidence, score.fragility, score.trigger, score.coverage,
            json.dumps(score.factors.model_dump()), score.momentum_state.value,
            score.df_dt, score.phase.value, score.phase_confidence,
            json.dumps(extra or {}),
        ))


def save_metrics(asof: date, metrics: list) -> None:
    with _conn() as c:
        for m in metrics:
            c.execute("""
                INSERT INTO metric_history (asof, name, factor, raw_value, source, note)
                VALUES (?,?,?,?,?,?)
            """, (asof.isoformat(), m.name, m.factor, m.raw_value, m.source, m.note))


def history_lookup(name: str, limit: int = 756) -> list[float]:
    with _conn() as c:
        rows = c.execute(
            "SELECT raw_value FROM metric_history WHERE name=? AND raw_value IS NOT NULL "
            "ORDER BY asof DESC LIMIT ?", (name, limit)
        ).fetchall()
    return [float(r["raw_value"]) for r in reversed(rows)]


def fragility_history(limit: int = 10) -> list[float]:
    with _conn() as c:
        rows = c.execute(
            "SELECT fragility FROM daily_scores ORDER BY asof DESC LIMIT ?", (limit,)
        ).fetchall()
    return [float(r["fragility"]) for r in reversed(rows)]


def latest_score() -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM daily_scores ORDER BY asof DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["factors"] = json.loads(d.pop("factors_json") or "{}")
    d["extra"] = json.loads(d.pop("payload_json") or "{}")
    return d


def latest_metrics(limit: int = 100) -> list[dict]:
    with _conn() as c:
        asof = c.execute("SELECT MAX(asof) FROM metric_history").fetchone()[0]
        if not asof:
            return []
        rows = c.execute(
            "SELECT name, factor, raw_value, source, note, asof FROM metric_history "
            "WHERE asof=? ORDER BY factor, name LIMIT ?", (asof, limit)
        ).fetchall()
    return [dict(r) for r in rows]
