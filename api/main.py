"""FastAPI backend for crash.netie.ai dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "static"

app = FastAPI(title="CASSANDRA", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


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


@app.get("/api/dashboard")
def dashboard():
    from src.store import latest_metrics, latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet — POST /api/run first")
    return {"score": score, "metrics": latest_metrics()}


@app.post("/api/run")
def run_cycle():
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
