"""SQLite persistence for DailyScore + metric history."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
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
        CREATE TABLE IF NOT EXISTS report_graph (
            asof TEXT PRIMARY KEY,
            generated_at TEXT,
            headline TEXT,
            report_json TEXT,
            graph_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_report_graph_generated ON report_graph(generated_at DESC);
        CREATE TABLE IF NOT EXISTS newspaper_bodies (
            asof TEXT NOT NULL,
            lang TEXT NOT NULL,
            col1_html TEXT,
            col2_html TEXT,
            col3_html TEXT,
            PRIMARY KEY (asof, lang)
        );
        CREATE TABLE IF NOT EXISTS digest_subscribers (
            email TEXT PRIMARY KEY,
            source TEXT,
            subscribed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contact_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            message TEXT NOT NULL,
            client_json TEXT,
            logged_at TEXT NOT NULL
        );
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


def score_by_offset_days(days: int) -> dict | None:
    """Nth most recent score (0 = latest)."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM daily_scores ORDER BY asof DESC LIMIT 1 OFFSET ?",
            (max(0, days),),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["factors"] = json.loads(d.pop("factors_json") or "{}")
    d["extra"] = json.loads(d.pop("payload_json") or "{}")
    return d


def score_on_or_before(asof: str) -> dict | None:
    """Latest score on or before YYYY-MM-DD."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM daily_scores WHERE asof <= ? ORDER BY asof DESC LIMIT 1",
            (asof,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["factors"] = json.loads(d.pop("factors_json") or "{}")
    d["extra"] = json.loads(d.pop("payload_json") or "{}")
    return d


def _fallback_highlights(asof: str | None = None) -> dict:
    score = score_on_or_before(asof) if asof else latest_score()
    if not score:
        return {
            "asof": None,
            "generated_at": None,
            "analog_date": "March 14, 2000",
            "analog_news": [],
            "today_news": [],
        }
    extra = score.get("extra") or {}
    return {
        "asof": score.get("asof"),
        "generated_at": None,
        "analog_date": extra.get("analog_date", "March 14, 2000"),
        "analog_news": extra.get("analog_news", []),
        "today_news": extra.get("today_news", []),
    }


def save_report_graph(
    asof: date | str,
    score: dict,
    *,
    sections: dict | None = None,
    highlights: dict | None = None,
    i18n: dict | None = None,
) -> None:
    """Persist date-addressable report snapshot + minimal knowledge graph."""
    asof_str = asof.isoformat() if hasattr(asof, "isoformat") else str(asof)
    generated_at = datetime.now().isoformat(timespec="seconds")
    sections = sections or {}
    highlights = highlights or {}
    i18n = i18n or {}
    report_json = {
        "asof": asof_str,
        "generated_at": generated_at,
        "headline": sections.get("headline") or "",
        "sub_headline": sections.get("sub_headline") or "",
        "sections": {
            "signal": sections.get("col1_html") or "",
            "direction": sections.get("col2_html") or "",
            "risk": sections.get("col3_html") or "",
        },
        "i18n": {
            lang: {
                "headline": block.get("headline", ""),
                "sub_headline": block.get("sub_headline", ""),
                "sections": {
                    "signal": block.get("col1_html") or "",
                    "direction": block.get("col2_html") or "",
                    "risk": block.get("col3_html") or "",
                },
                "caveat": block.get("caveat", ""),
            }
            for lang, block in i18n.items()
        },
        "score": score,
        "highlights": {
            "analog_date": highlights.get("analog_date") or "March 14, 2000",
            "analog_news": highlights.get("analog_news") or [],
            "today_news": highlights.get("today_news") or [],
        },
    }
    graph_json = {
        "nodes": [
            {"id": f"report:{asof_str}", "type": "ReportEdition", "asof": asof_str, "generated_at": generated_at},
            {"id": f"score:{asof_str}", "type": "DailyScore", "crs": score.get("crs"), "band": score.get("band")},
        ],
        "edges": [
            {"source": f"report:{asof_str}", "target": f"score:{asof_str}", "relation": "HAS_SCORE"},
        ],
    }
    for idx, item in enumerate((highlights.get("today_news") or [])[:8], start=1):
        nid = f"news:{asof_str}:{idx}"
        graph_json["nodes"].append({
            "id": nid,
            "type": "NewsItem",
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "asof": item.get("asof", ""),
        })
        graph_json["edges"].append({
            "source": f"report:{asof_str}",
            "target": nid,
            "relation": "CITED_BY",
        })
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO report_graph (asof, generated_at, headline, report_json, graph_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                asof_str,
                generated_at,
                report_json.get("headline", ""),
                json.dumps(report_json),
                json.dumps(graph_json),
            ),
        )


def report_archive(limit: int = 60) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT asof, generated_at, headline FROM report_graph ORDER BY asof DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def report_by_asof(asof: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT asof, generated_at, headline, report_json, graph_json FROM report_graph WHERE asof = ?",
            (asof,),
        ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["report"] = json.loads(out.pop("report_json") or "{}")
    out["graph"] = json.loads(out.pop("graph_json") or "{}")
    return out


def latest_highlights(asof: str | None = None) -> dict:
    """News ranking + analog metadata for selected edition date."""
    if asof:
        picked = report_by_asof(asof)
        if picked:
            report = picked.get("report") or {}
            hi = report.get("highlights") or {}
            return {
                "asof": picked.get("asof"),
                "generated_at": picked.get("generated_at"),
                "headline": report.get("headline", ""),
                "analog_date": hi.get("analog_date", "March 14, 2000"),
                "analog_news": hi.get("analog_news", []),
                "today_news": hi.get("today_news", []),
            }
    rows = report_archive(limit=1)
    if rows:
        picked = report_by_asof(rows[0]["asof"])
        if picked:
            report = picked.get("report") or {}
            hi = report.get("highlights") or {}
            return {
                "asof": picked.get("asof"),
                "generated_at": picked.get("generated_at"),
                "headline": report.get("headline", ""),
                "analog_date": hi.get("analog_date", "March 14, 2000"),
                "analog_news": hi.get("analog_news", []),
                "today_news": hi.get("today_news", []),
            }
    return _fallback_highlights(asof)


def save_newspaper_body(
    asof: date | str,
    lang: str,
    col1_html: str,
    col2_html: str,
    col3_html: str = "",
) -> None:
    """Persist pipeline-generated newspaper body for (date, lang) tuple."""
    asof_str = asof.isoformat() if hasattr(asof, "isoformat") else str(asof)
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO newspaper_bodies (asof, lang, col1_html, col2_html, col3_html)
            VALUES (?, ?, ?, ?, ?)
            """,
            (asof_str, lang, col1_html, col2_html, col3_html),
        )


def get_newspaper_body(asof: date | str, lang: str) -> dict | None:
    asof_str = asof.isoformat() if hasattr(asof, "isoformat") else str(asof)
    with _conn() as c:
        row = c.execute(
            "SELECT asof, lang, col1_html, col2_html, col3_html FROM newspaper_bodies WHERE asof = ? AND lang = ?",
            (asof_str, lang),
        ).fetchone()
    return dict(row) if row else None


def save_digest_subscriber(email: str, source: str = "newspaper") -> bool:
    """Insert email if new. Returns True if newly added."""
    email = email.strip().lower()
    if not email or "@" not in email:
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO digest_subscribers (email, source, subscribed_at) VALUES (?,?,?)",
            (email, source[:32], now),
        )
        return cur.rowcount > 0


def log_contact(email: str | None, message: str, client: dict | None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO contact_log (email, message, client_json, logged_at) VALUES (?,?,?,?)",
            (email, message[:4000], json.dumps(client or {}), now),
        )
        return int(cur.lastrowid)


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


def log_agent_gate_block(message: str, score: float, reason: str) -> None:
    """Persist blocked agent attempts for future classifier training."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_gate_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL,
                message TEXT NOT NULL,
                score REAL,
                reason TEXT NOT NULL
            )
        """)
        c.execute(
            "INSERT INTO agent_gate_log (logged_at, message, score, reason) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), message[:2000], score, reason),
        )
