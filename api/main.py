"""FastAPI backend for crash.netie.ai dashboard."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import FREE_DELAY_DAYS, FIRST_SUB_TRIAL_DAYS, gate_score, get_user_tier, resolve_score_dict, subscription_checkout_options

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
    extra = score.get("extra") or {}
    out = {
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
        "capex_cut_nlp": extra.get("capex_cut_nlp"),
    }
    if score.get("delayed"):
        out["delayed"] = True
        out["delay_days"] = score.get("delay_days", 2)
    return out


def _static_page(name: str) -> FileResponse:
    path = WEB / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found")
    return FileResponse(path)


def _coming_soon(page: str, **params: str) -> RedirectResponse:
    q = f"page={page}"
    for k, v in params.items():
        if v:
            q += f"&{k}={v}"
    return RedirectResponse(f"/static/coming-soon.html?{q}")


KNOWN_STOCK_DEMOS = frozenset({"NOW", "MU"})


def _score_for_tier_asof(tier: str, asof: str | None) -> dict | None:
    from src.store import latest_score, score_by_offset_days, score_on_or_before

    if not asof:
        return resolve_score_dict(tier)

    if tier in ("report", "briefing", "agent"):
        return score_on_or_before(asof) or latest_score()

    delayed = score_by_offset_days(FREE_DELAY_DAYS) or latest_score()
    if not delayed:
        return None
    delayed_asof = delayed.get("asof")
    if delayed_asof and asof <= delayed_asof:
        picked = score_on_or_before(asof)
        return picked or delayed
    out = dict(delayed)
    out["delayed"] = True
    out["delay_days"] = FREE_DELAY_DAYS
    return out


@app.get("/docs/methodology")
def methodology_doc():
    return _static_page("docs-methodology.html")


@app.get("/agent")
@app.get("/agent-chat")
def agent_page():
    return _coming_soon("agent-chat")


@app.get("/platform")
def platform_page():
    return _coming_soon("platform")


@app.get("/docs/methodology/raw")
def methodology_raw():
    path = ROOT / "docs" / "METHODOLOGY.md"
    if not path.exists():
        raise HTTPException(404, "Methodology doc not found")
    return FileResponse(path, media_type="text/markdown; charset=utf-8")


@app.get("/docs/api")
def docs_api():
    return _static_page("docs-api.html")


@app.get("/docs/institutional")
def docs_institutional():
    return _static_page("docs-institutional.html")


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
    sym = ticker.upper()
    path = WEB / "stocks" / sym / "index.html"
    if sym in KNOWN_STOCK_DEMOS and path.exists():
        return FileResponse(path)
    return _coming_soon("stock-agent", ticker=sym)


@app.get("/api/health")
def health():
    from src.store import DB
    return {"status": "ok", "store": str(DB), "store_exists": DB.exists()}


@app.get("/api/geo")
def geo(x_country: str | None = Header(default=None, alias="X-Country")):
    country = x_country or os.getenv("DEV_GEO_COUNTRY", "US")
    return {"country": country.upper()[:2]}


@app.get("/api/latest")
def latest(
    asof: str | None = Query(default=None, description="YYYY-MM-DD edition date"),
    tier: str = Depends(get_user_tier),
):
    raw = _score_for_tier_asof(tier, asof)
    if not raw:
        raise HTTPException(404, "No score yet — run pipeline locally")
    return _compact_score(gate_score(raw, tier))


@app.get("/api/report/highlights")
def report_highlights(
    asof: str | None = Query(default=None, description="YYYY-MM-DD edition date"),
    tier: str = Depends(get_user_tier),
):
    from src.store import latest_highlights

    score = _score_for_tier_asof(tier, asof)
    if not score:
        return latest_highlights(None)
    picked_asof = score.get("asof")
    out = latest_highlights(picked_asof)
    if score.get("delayed"):
        out["delayed"] = True
        out["delay_days"] = score.get("delay_days", FREE_DELAY_DAYS)
    return out


@app.get("/api/dashboard")
def dashboard(
    asof: str | None = Query(default=None, description="YYYY-MM-DD edition date"),
    tier: str = Depends(get_user_tier),
):
    from src.store import latest_metrics
    raw = _score_for_tier_asof(tier, asof)
    if not raw:
        raise HTTPException(404, "No score yet — POST /api/run first")
    score = gate_score(raw, tier)
    metrics = latest_metrics() if tier in ("report", "briefing", "agent") else []
    return {"score": score, "metrics": metrics, "tier": tier}


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


@app.get("/api/newspaper-body")
def newspaper_body(
    date: str | None = Query(default=None, description="YYYY-MM-DD edition date"),
    lang: str = Query(default="en"),
):
    from datetime import date as dt_date
    from src.store import get_newspaper_body, latest_score
    d = dt_date.fromisoformat(date) if date else None
    if d is None:
        latest = latest_score()
        if not latest or not latest.get("asof"):
            raise HTTPException(404, "No pipeline body for this date/lang")
        d = dt_date.fromisoformat(str(latest["asof"]))
    body = get_newspaper_body(d, lang)
    if not body:
        raise HTTPException(404, "No pipeline body for this date/lang")
    return body


@app.get("/api/indices")
def api_indices():
    from src.market_snapshot import index_snapshot
    return index_snapshot()


@app.get("/api/watchlist")
def api_watchlist(user: str = Query(default="local")):
    from src.watchlist import get_watchlist
    return get_watchlist(user)


@app.post("/api/watchlist/update")
def api_watchlist_update(
    body: dict = Body(...),
):
    from src.watchlist import update_watchlist
    user = str(body.get("user") or "local")
    tickers = body.get("tickers") or []
    if not isinstance(tickers, list):
        raise HTTPException(400, "tickers must be a list")
    return update_watchlist(user, tickers)


@app.get("/api/movers")
def api_movers(
    tf: str = Query(default="1D"),
    sector: str = Query(default="tech,semis"),
    limit: int = Query(default=10, ge=1, le=20),
):
    from src.market_snapshot import top_movers
    return top_movers(tf=tf, sector=sector, limit=limit)


@app.get("/api/signals/fear_greed")
def api_fear_greed():
    from src.market_snapshot import fear_greed
    return fear_greed()


@app.post("/api/agent/gate")
def api_agent_gate(body: dict = Body(...)):
    """Pre-LLM relevance gate for chat widget."""
    from src.store import log_agent_gate_block
    from src.tools.agent_gate import gate_message

    text = str(body.get("message") or "")
    result = gate_message(text)
    if not result.allowed:
        log_agent_gate_block(text, result.score, result.reason)
    return {
        "allowed": result.allowed,
        "score": result.score,
        "reason": result.reason,
        "response": result.response,
    }


@app.post("/api/agent/chat")
def api_agent_chat(
    body: dict = Body(...),
    tier: str = Depends(get_user_tier),
):
    """Compact-context desk chat — trading engine tone, max ~320 tokens."""
    from src.tools.agent_chat import chat

    text = str(body.get("message") or "")
    if not text.strip():
        raise HTTPException(400, "message required")
    return chat(text, tier=tier)


@app.post("/api/digest/signup")
def digest_signup(body: dict = Body(...)):
    """Free daily digest — no payment redirect."""
    from src.store import save_digest_subscriber

    email = str(body.get("email") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    source = str(body.get("source") or "newspaper")[:32]
    is_new = save_digest_subscriber(email, source)
    return {
        "ok": True,
        "new": is_new,
        "message": (
            "You're on the free daily list. Check your inbox on the next trading-day edition."
            if is_new
            else "You're already on the free daily list."
        ),
    }


@app.get("/api/diagnostics")
def api_diagnostics():
    from src.diagnostics import server_snapshot
    return server_snapshot()


@app.post("/api/contact")
def api_contact(body: dict = Body(...)):
    from src.diagnostics import format_contact_body
    from src.store import log_contact

    message = str(body.get("message") or "").strip()
    if len(message) < 4:
        raise HTTPException(400, "Message too short")
    email = str(body.get("email") or "").strip() or None
    client = body.get("client") if isinstance(body.get("client"), dict) else {}
    log_id = log_contact(email, message, client)
    plain, html = format_contact_body(message=message, email=email, client=client)
    sent = False
    to_addr = os.getenv("CONTACT_TO", "desk@netie.ai")
    try:
        from src.newsletter.send import send_edition
        send_edition(
            to=to_addr,
            subject=f"[Cassandra contact #{log_id}] {email or 'anonymous'}",
            html=html,
            text=plain,
            tags={"type": "contact"},
        )
        sent = True
    except Exception:
        pass
    return {"ok": True, "logged_id": log_id, "email_sent": sent}


@app.get("/api/subscribe/options")
def subscribe_options(
    tier: str = Query(default="report"),
    first_sub: bool = Query(default=True, description="First-time subscriber eligible for trial"),
):
    """Checkout flags for payment providers — 7-day trial on first subscription."""
    opts = subscription_checkout_options(tier, is_first_subscription=first_sub)
    opts["trial_message"] = (
        f"{FIRST_SUB_TRIAL_DAYS} days free for new subscribers"
        if opts["first_subscriber_trial"]
        else "No trial — returning subscriber"
    )
    return opts


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


@app.get("/api/report/archive")
def report_archive(limit: int = 90):
    from src.store import report_archive
    return {"editions": report_archive(limit=max(1, min(limit, 365)))}


@app.get("/api/report/edition")
def report_edition(
    asof: str = Query(..., description="YYYY-MM-DD"),
    lang: str = Query(default="en"),
):
    from src.store import report_by_asof
    out = report_by_asof(asof)
    if not out:
        raise HTTPException(404, "Edition not found")
    lang = lang.lower()[:2]
    report = out.get("report") or {}
    if lang != "en" and report.get("i18n", {}).get(lang):
        block = report["i18n"][lang]
        out["report"] = {
            **report,
            "headline": block.get("headline", report.get("headline")),
            "sub_headline": block.get("sub_headline", report.get("sub_headline")),
            "sections": block.get("sections", report.get("sections")),
            "lang": lang,
        }
    return out
