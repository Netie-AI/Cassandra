"""FastAPI backend for crash.netie.ai dashboard."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "static"

app = FastAPI(title="CASSANDRA", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


def _require_pipeline_key(x_pipeline_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("PIPELINE_KEY")
    if not expected:
        return
    if x_pipeline_key != expected:
        raise HTTPException(401, "Invalid or missing X-Pipeline-Key")


def _compact_score(score: dict) -> dict:
    return {
        "crs": score["crs"],
        "band": score["band"],
        "fragility": score["fragility"],
        "trigger": score["trigger"],
        "phase": score["phase"],
        "phase_confidence": score["phase_confidence"],
        "coverage": score["coverage"],
        "asof": score["asof"],
        "band_halfwidth": score.get("band_halfwidth"),
        "confidence": score.get("confidence"),
        "factors": score.get("factors"),
        "momentum_state": score.get("momentum_state"),
    }


@app.get("/")
def index():
    idx = WEB / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"service": "CASSANDRA", "docs": "/docs"}


@app.get("/api/health")
def health():
    from src.store import DB
    return {"status": "ok", "store": str(DB), "store_exists": DB.exists()}


@app.get("/api/geo")
def geo(x_country: str | None = Header(default=None, alias="X-Country")):
    """Local dev stub — Cloudflare Worker returns request.cf.country in production."""
    country = x_country or os.getenv("DEV_GEO_COUNTRY", "US")
    return {"country": country.upper()[:2]}


@app.get("/api/latest")
def latest():
    """Public score snapshot (same shape as KV / cf_publish payload + display fields)."""
    from src.store import latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet — run pipeline locally")
    return _compact_score(score)


@app.get("/api/dashboard")
def dashboard():
    from src.store import latest_metrics, latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet — POST /api/run first")
    return {"score": score, "metrics": latest_metrics()}


@app.post("/api/run")
def run_cycle(_: None = Depends(_require_pipeline_key)):
    from src.pipeline import run_pipeline
    score = run_pipeline()
    return {"ok": True, "crs": score.crs, "band": score.band_label, "asof": str(score.asof)}


@app.get("/api/scores/history")
def score_history(limit: int = 30):
    import sqlite3
    from src.store import DB
    if not DB.exists():
        return {"history": []}
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT asof, crs, band, fragility, trigger, confidence FROM daily_scores "
            "ORDER BY asof DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"history": [dict(r) for r in rows]}
