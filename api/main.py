"""FastAPI backend for crash.netie.ai dashboard."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .auth import gate_score, get_user_tier

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "static"

app = FastAPI(title="CASSANDRA", version="0.2.0")
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


def _static_page(name: str) -> FileResponse:
    path = WEB / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found")
    return FileResponse(path)


@app.get("/")
def index():
    return _static_page("index.html")


@app.get("/newspaper-report")
def newspaper_report():
    return _static_page("newspaper-report.html")


@app.get("/pricing")
@app.get("/subscribe")
def pricing():
    return _static_page("pricing.html")


@app.get("/stocks/{ticker}")
def stock_demo(ticker: str):
    path = WEB / "stocks" / ticker.upper() / "index.html"
    if path.exists():
        return FileResponse(path)
    raise HTTPException(404, f"Demo page for {ticker} not found")


@app.get("/api/health")
def health():
    from src.store import DB
    return {"status": "ok", "store": str(DB), "store_exists": DB.exists()}


@app.get("/api/geo")
def geo(x_country: str | None = Header(default=None, alias="X-Country")):
    country = x_country or os.getenv("DEV_GEO_COUNTRY", "US")
    return {"country": country.upper()[:2]}


@app.get("/api/latest")
def latest():
    from src.store import latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet — run pipeline locally")
    return _compact_score(score)


@app.get("/api/dashboard")
def dashboard(tier: str = Depends(get_user_tier)):
    from src.store import latest_metrics, latest_score
    raw = latest_score()
    if not raw:
        raise HTTPException(404, "No score yet — POST /api/run first")
    score = gate_score(raw, tier)
    return {"score": score, "metrics": latest_metrics(), "tier": tier}


@app.get("/api/report/sections")
def report_sections(tier: str = Depends(get_user_tier)):
    from src.report import generate_report_sections
    from src.store import latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet")
    effective = tier if tier in ("report", "briefing", "agent") else "free"
    return generate_report_sections(score, effective)


@app.get("/api/report/html")
def report_html(tier: str = Depends(get_user_tier)):
    from src.report import generate_report_sections, render_report_html
    from src.store import latest_score
    score = latest_score()
    if not score:
        raise HTTPException(404, "No score yet")
    effective = tier if tier in ("report", "briefing", "agent") else "report"
    sections = generate_report_sections(score, effective)
    return HTMLResponse(render_report_html(sections))


@app.get("/api/account/vouchers")
def vouchers(ref: str | None = Query(default=None)):
    """Referral voucher stub — Supabase wiring in PARKING_LOT.md."""
    code = ref or secrets.token_hex(4).upper()
    return {
        "referral_code": f"NETIE-{code[:6]}",
        "referral_rule": "When a referral subscribes, referrer gets 7 days free API — activate in account vouchers.",
        "vouchers": [],
        "activate_url": "/subscribe?voucher=pending",
    }


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
