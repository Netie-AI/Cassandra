"""SQLite persistence for DailyScore + metric history."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "store" / "scores.sqlite"

DIGEST_DOUBLE_OPTIN = os.getenv("DIGEST_DOUBLE_OPTIN", "false").lower() == "true"


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
            subscribed_at TEXT NOT NULL,
            confirmed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS contact_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            message TEXT NOT NULL,
            client_json TEXT,
            logged_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            asof TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            crs REAL, band TEXT, phase TEXT, phase_confidence REAL,
            fragility REAL, trigger REAL, coverage REAL,
            capex_cut_nlp REAL,
            analog_match TEXT,
            newsletter_sent INTEGER NOT NULL DEFAULT 0,
            newsletter_sent_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_completed ON pipeline_runs(completed_at DESC);
    """)
    try:
        c.execute("ALTER TABLE digest_subscribers ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE digest_subscribers ADD COLUMN confirm_token TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE digest_subscribers ADD COLUMN unsub_token TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE digest_subscribers ADD COLUMN last_sent_at TEXT")
    except sqlite3.OperationalError:
        pass
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


def get_score_history(start: str, end: str) -> list[dict]:
    """CRS rows between start and end (inclusive), ascending by asof."""
    with _conn() as c:
        rows = c.execute(
            "SELECT asof, crs, band, fragility, trigger, phase, phase_confidence, coverage "
            "FROM daily_scores WHERE asof >= ? AND asof <= ? ORDER BY asof ASC",
            (start, end),
        ).fetchall()
    return [
        {
            "date": r["asof"],
            "crs": r["crs"],
            "phase": r["phase"],
            "f": r["fragility"],
            "t": r["trigger"],
            "band": r["band"],
            "coverage": r["coverage"],
        }
        for r in rows
    ]


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


def save_digest_subscriber(email: str, source: str = "newspaper") -> tuple[bool, bool, str | None]:
    """Insert email if new. Returns (is_new, confirmed, unsub_token)."""
    from src.tools._env import load_env

    load_env()
    double_optin = os.getenv("DIGEST_DOUBLE_OPTIN", "false").lower() == "true"
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, False, None
    now = datetime.now(timezone.utc).isoformat()
    confirmed = 0 if double_optin else 1
    token = secrets.token_urlsafe(32) if double_optin else None
    unsub = secrets.token_urlsafe(16)
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO digest_subscribers "
            "(email, source, subscribed_at, confirmed, confirm_token, unsub_token) VALUES (?,?,?,?,?,?)",
            (email, source[:32], now, confirmed, token, unsub),
        )
        is_new = cur.rowcount > 0
        if not is_new:
            if double_optin:
                c.execute(
                    "UPDATE digest_subscribers SET confirm_token = ? WHERE email = ? AND confirmed = 0",
                    (token or secrets.token_urlsafe(32), email),
                )
            else:
                c.execute("UPDATE digest_subscribers SET confirmed = 1 WHERE email = ?", (email,))
            row = c.execute(
                "SELECT unsub_token FROM digest_subscribers WHERE email = ?", (email,)
            ).fetchone()
            if row and not row["unsub_token"]:
                c.execute(
                    "UPDATE digest_subscribers SET unsub_token = ? WHERE email = ?",
                    (secrets.token_urlsafe(16), email),
                )
        row = c.execute("SELECT confirmed, unsub_token FROM digest_subscribers WHERE email = ?", (email,)).fetchone()
        unsub_out = str(row["unsub_token"]) if row and row["unsub_token"] else unsub
        return is_new, bool(row["confirmed"]) if row else False, unsub_out


def confirm_digest_subscriber(token: str) -> bool:
    """Confirm subscriber by token. Returns True if matched."""
    token = token.strip()
    if not token:
        return False
    with _conn() as c:
        row = c.execute(
            "SELECT email FROM digest_subscribers WHERE confirm_token = ? AND confirmed = 0",
            (token,),
        ).fetchone()
        if not row:
            return False
        c.execute(
            "UPDATE digest_subscribers SET confirmed = 1, confirm_token = NULL WHERE confirm_token = ?",
            (token,),
        )
        return True


def count_confirmed_digest_subscribers() -> int:
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM digest_subscribers WHERE confirmed = 1").fetchone()
    return int(row["n"]) if row else 0


def recent_digest_subscribers(limit: int = 5) -> list[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT email FROM digest_subscribers WHERE confirmed = 1 ORDER BY subscribed_at DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    return [str(r["email"]) for r in rows]


def list_confirmed_digest_subscribers(limit: int = 10_000) -> list[str]:
    """Return emails with confirmed=1 only."""
    return [r["email"] for r in list_digest_recipients(limit)]


def list_digest_recipients(limit: int = 10_000) -> list[dict]:
    """Confirmed subscribers with unsubscribe tokens."""
    with _conn() as c:
        rows = c.execute(
            "SELECT email, unsub_token FROM digest_subscribers WHERE confirmed = 1 ORDER BY subscribed_at LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    out: list[dict] = []
    for row in rows:
        email = str(row["email"])
        token = row["unsub_token"]
        if not token:
            token = secrets.token_urlsafe(16)
            with _conn() as c2:
                c2.execute(
                    "UPDATE digest_subscribers SET unsub_token = ? WHERE email = ?",
                    (token, email),
                )
        out.append({"email": email, "unsub_token": token})
    return out


def unsubscribe_digest(token: str) -> str | None:
    """Unsubscribe by token. Returns email when successful, else None."""
    token = token.strip()
    if not token:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT email FROM digest_subscribers WHERE unsub_token = ? AND confirmed = 1",
            (token,),
        ).fetchone()
        if not row:
            return None
        email = str(row["email"])
        c.execute(
            "UPDATE digest_subscribers SET confirmed = 0 WHERE unsub_token = ?",
            (token,),
        )
        return email


def mark_digest_sent(emails: list[str]) -> None:
    if not emails:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        for email in emails:
            c.execute(
                "UPDATE digest_subscribers SET last_sent_at = ? WHERE email = ?",
                (now, email),
            )


def get_last_pipeline_completed_at() -> datetime | None:
    with _conn() as c:
        row = c.execute(
            "SELECT completed_at FROM pipeline_runs ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
    if not row or not row["completed_at"]:
        return None
    try:
        raw = str(row["completed_at"]).replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def log_newsletter_send(email: str, subject: str, *, ok: bool, detail: str = "") -> None:
    """Audit trail for batch sends — stored in contact_log."""
    msg = f"[newsletter] subject={subject!r} ok={ok} {detail}".strip()
    log_contact(email, msg, {"type": "newsletter_dispatch"})


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


def _run_summary(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "timestamp": row["completed_at"],
        "asof": row["asof"],
        "crs": row.get("crs"),
        "phase": row.get("phase"),
        "phase_conf": row.get("phase_confidence"),
        "f": row.get("fragility"),
        "t": row.get("trigger"),
        "coverage": row.get("coverage"),
        "capex_cut_nlp": row.get("capex_cut_nlp"),
        "analog_match": row.get("analog_match"),
        "newsletter_sent": bool(row.get("newsletter_sent")),
    }


def record_pipeline_run(score: dict) -> str:
    """Append ops run log entry; returns run_id."""
    from .analog import cosine_match

    asof = str(score.get("asof") or date.today().isoformat())
    completed_at = datetime.now(timezone.utc).isoformat()
    run_id = f"{asof}T{completed_at[11:19].replace(':', '')}Z"
    extra = score.get("extra") or {}
    capex = extra.get("capex_cut_nlp")
    if capex is None:
        capex = (extra.get("orchestrator") or {}).get("capex_cut_nlp")
    key, _sim = cosine_match(
        float(score.get("crs") or 0),
        float(score.get("fragility") or 0),
        float(score.get("trigger") or 0),
    )
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO pipeline_runs
            (run_id, asof, completed_at, crs, band, phase, phase_confidence,
             fragility, trigger, coverage, capex_cut_nlp, analog_match,
             newsletter_sent, newsletter_sent_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,NULL)
            """,
            (
                run_id,
                asof,
                completed_at,
                score.get("crs"),
                score.get("band"),
                score.get("phase"),
                score.get("phase_confidence"),
                score.get("fragility"),
                score.get("trigger"),
                score.get("coverage"),
                capex,
                key,
            ),
        )
    return run_id


def get_run_history(limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM pipeline_runs ORDER BY completed_at DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    if rows:
        return [_run_summary(dict(r)) for r in rows]
    from .analog import cosine_match

    with _conn() as c:
        scores = c.execute(
            "SELECT asof, crs, band, fragility, trigger, coverage, phase, phase_confidence, payload_json "
            "FROM daily_scores ORDER BY asof DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
    out: list[dict] = []
    for r in scores:
        d = dict(r)
        extra = json.loads(d.pop("payload_json") or "{}")
        ts = f"{d['asof']}T16:00:00+00:00"
        with _conn() as c2:
            rg = c2.execute(
                "SELECT generated_at FROM report_graph WHERE asof = ?", (d["asof"],)
            ).fetchone()
        if rg and rg["generated_at"]:
            ts = rg["generated_at"]
        key, _ = cosine_match(
            float(d.get("crs") or 0),
            float(d.get("fragility") or 0),
            float(d.get("trigger") or 0),
        )
        out.append({
            "run_id": d["asof"],
            "timestamp": ts,
            "asof": d["asof"],
            "crs": d.get("crs"),
            "phase": d.get("phase"),
            "phase_conf": d.get("phase_confidence"),
            "f": d.get("fragility"),
            "t": d.get("trigger"),
            "coverage": d.get("coverage"),
            "capex_cut_nlp": extra.get("capex_cut_nlp"),
            "analog_match": key,
            "newsletter_sent": False,
        })
    return out


def get_run_detail(run_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        hist = get_run_history(90)
        match = next((h for h in hist if h["run_id"] == run_id), None)
        if not match:
            match = next((h for h in hist if h["asof"] == run_id), None)
        if not match:
            return None
        asof = match["asof"]
        with _conn() as c2:
            score_row = c2.execute(
                "SELECT * FROM daily_scores WHERE asof = ?", (asof,)
            ).fetchone()
        if not score_row:
            return None
        score = dict(score_row)
        extra = json.loads(score.pop("payload_json") or "{}")
        score["extra"] = extra
        score["factors"] = json.loads(score.pop("factors_json") or "{}")
        bodies = {}
        for lang in ("en", "zh", "ms"):
            b = get_newspaper_body(asof, lang)
            if b:
                bodies[lang] = b
        return {
            **match,
            "band": score.get("band"),
            "newspaper": bodies,
            "last_newsletter_sent": get_last_newsletter_sent(),
            "subscriber_count": count_confirmed_digest_subscribers(),
        }
    summary = _run_summary(dict(row))
    asof = summary["asof"]
    bodies = {}
    for lang in ("en", "zh", "ms"):
        b = get_newspaper_body(asof, lang)
        if b:
            bodies[lang] = b
    return {
        **summary,
        "band": row["band"],
        "newspaper": bodies,
        "last_newsletter_sent": get_last_newsletter_sent(),
        "subscriber_count": count_confirmed_digest_subscribers(),
    }


def mark_newsletter_sent(run_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE pipeline_runs SET newsletter_sent = 1, newsletter_sent_at = ? WHERE run_id = ?",
            (now, run_id),
        )


def was_newsletter_sent(run_id: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT newsletter_sent FROM pipeline_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return bool(row and row["newsletter_sent"])


def get_last_newsletter_sent() -> str | None:
    with _conn() as c:
        row = c.execute(
            "SELECT newsletter_sent_at FROM pipeline_runs "
            "WHERE newsletter_sent = 1 ORDER BY newsletter_sent_at DESC LIMIT 1"
        ).fetchone()
    return row["newsletter_sent_at"] if row else None


def latest_run_id() -> str | None:
    runs = get_run_history(1)
    return runs[0]["run_id"] if runs else None


def save_report_markdown(edition: str, lang: str, body: str, run_id: str) -> Path:
    """Persist dated edition markdown under reports/ (local only, gitignored)."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slot = "0600" if edition == "morning" else "1800"
    path = ROOT / "reports" / f"{date}-{slot}-{lang.upper()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    front = (
        f"---\nrun_id: {run_id}\ndate: {date}\nedition: {edition}\nlang: {lang}\n---\n\n"
    )
    path.write_text(front + body, encoding="utf-8")
    return path


def list_report_markdown(*, date: str, edition: str) -> list[str]:
    slot = "0600" if edition == "morning" else "1800"
    folder = ROOT / "reports"
    if not folder.exists():
        return []
    prefix = f"{date}-{slot}-"
    return sorted(p.name for p in folder.glob(f"{prefix}*.md"))


def read_report_markdown(filename: str) -> str | None:
    safe = Path(filename).name
    path = ROOT / "reports" / safe
    if not path.exists() or path.suffix != ".md":
        return None
    return path.read_text(encoding="utf-8")


def append_signal_history(score_obj: dict) -> None:
    path = ROOT / "knowledge" / "graph" / "signal-history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(score_obj) + "\n")


def save_agent_outputs(edition: str, bundles: list, run_id: str) -> Path:
    """Structured subagent reads for audit + knowledge graph."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slot = "0600" if edition == "morning" else "1800"
    path = ROOT / "knowledge" / "agents" / f"{date}-{slot}-agent-outputs.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"run_id: {run_id}",
        f"date: {date}",
        f"edition: {edition}",
        "---",
        "",
        f"# Agent outputs · {date} · {edition}",
        "",
    ]
    for bundle in bundles:
        name = type(bundle).__name__
        lines.append(f"## {name}")
        try:
            payload = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else {}
            lines.append("```json")
            lines.append(json.dumps(payload, indent=2)[:12000])
            lines.append("```")
        except Exception as exc:
            lines.append(f"_serialize error: {exc}_")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


_ABUSE_LIMIT = 10


def record_agent_abuse(actor_key: str, reason: str) -> int:
    """Increment suspicious-attempt counter; returns new strike count."""
    actor_key = (actor_key or "unknown")[:128]
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_abuse_log (
                actor_key TEXT PRIMARY KEY,
                strikes INTEGER NOT NULL DEFAULT 0,
                last_reason TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        row = c.execute(
            "SELECT strikes FROM agent_abuse_log WHERE actor_key = ?", (actor_key,)
        ).fetchone()
        strikes = int(row["strikes"]) + 1 if row else 1
        c.execute(
            """
            INSERT OR REPLACE INTO agent_abuse_log (actor_key, strikes, last_reason, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (actor_key, strikes, reason[:200], now),
        )
    return strikes


def is_agent_banned(actor_key: str) -> bool:
    actor_key = (actor_key or "unknown")[:128]
    with _conn() as c:
        try:
            row = c.execute(
                "SELECT strikes FROM agent_abuse_log WHERE actor_key = ?", (actor_key,)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
    return bool(row and int(row["strikes"]) >= _ABUSE_LIMIT)


def _ensure_agent_usage_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_usage (
            email TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (email, usage_date)
        )
    """)


def get_agent_usage(email: str, date: str) -> int:
    """How many agents has this user generated today."""
    email = (email or "anonymous").strip().lower()[:256]
    date = (date or "")[:10]
    with _conn() as c:
        _ensure_agent_usage_table(c)
        row = c.execute(
            "SELECT count FROM agent_usage WHERE email = ? AND usage_date = ?",
            (email, date),
        ).fetchone()
    return int(row["count"]) if row else 0


def increment_agent_usage(email: str, date: str) -> int:
    """Increment counter, return new count."""
    email = (email or "anonymous").strip().lower()[:256]
    date = (date or "")[:10]
    with _conn() as c:
        _ensure_agent_usage_table(c)
        c.execute(
            """
            INSERT INTO agent_usage (email, usage_date, count) VALUES (?, ?, 1)
            ON CONFLICT(email, usage_date) DO UPDATE SET count = count + 1
            """,
            (email, date),
        )
        row = c.execute(
            "SELECT count FROM agent_usage WHERE email = ? AND usage_date = ?",
            (email, date),
        ).fetchone()
    return int(row["count"]) if row else 1
