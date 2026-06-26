"""FastAPI backend for crash.netie.ai dashboard."""
from __future__ import annotations

import logging
import os
import secrets
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    FREE_DELAY_DAYS,
    FIRST_SUB_TRIAL_DAYS,
    gate_score,
    get_user_tier,
    is_master,
    normalize_tier,
    resolve_score_dict,
    subscription_checkout_options,
    tier_caps,
)
from .rate_limit import check as rate_limit_check
from .middleware.ip_guard import check_ip as ip_guard_check, log_ip_event

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "static"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools._env import load_env
    from .startup import log_activation_state

    load_env()
    log_activation_state()
    yield


app = FastAPI(title="CASSANDRA", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        action = "api_default"
        if path.startswith("/api/auth/"):
            action = "auth_attempt"
        elif path == "/api/agent/generate":
            action = "agent_generate"
        allowed, reason = ip_guard_check(ip, action)
        log_ip_event(ip, action, allowed, reason)
        if not allowed:
            return JSONResponse({"error": reason}, status_code=429)
        if not rate_limit_check(path, ip):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
    return await call_next(request)

if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


def _require_pipeline_key(x_pipeline_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("PIPELINE_KEY")
    if not expected:
        return
    if x_pipeline_key != expected:
        raise HTTPException(401, "Invalid or missing X-Pipeline-Key")


def _require_ops(
    request: Request,
    x_pipeline_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Ops routes: localhost always allowed; remote needs PIPELINE_KEY."""
    host = request.client.host if request.client else ""
    if host in ("127.0.0.1", "::1"):
        return
    expected = os.getenv("PIPELINE_KEY")
    if not expected:
        raise HTTPException(403, "Set PIPELINE_KEY for remote ops access")
    if x_pipeline_key == expected:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token == expected:
        return
    raise HTTPException(401, "Unauthorized")


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
    return RedirectResponse("/agents")


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


@app.get("/agents")
@app.get("/agents.html")
def agents_page():
    return _static_page("agents.html")


@app.get("/pricing")
@app.get("/subscribe")
def pricing():
    return _static_page("pricing.html")


@app.get("/privacy")
def privacy_page():
    return _static_page("privacy.html")


@app.get("/terms")
def terms_page():
    return _static_page("terms.html")


@app.get("/login")
def login_page():
    return _static_page("login.html")


@app.get("/signup")
def signup_page():
    return _static_page("signup.html")


@app.get("/404")
def page_not_found():
    return _static_page("404.html")


@app.get("/500")
def page_server_error():
    return _static_page("500.html")


@app.get("/ops")
def ops_page():
    return _static_page("ops.html")


@app.get("/stocks/{ticker}")
def stock_demo(ticker: str):
    sym = ticker.upper()
    path = WEB / "stocks" / sym / "index.html"
    if sym in KNOWN_STOCK_DEMOS and path.exists():
        return FileResponse(path)
    return _coming_soon("stock-agent", ticker=sym)


@app.get("/api/health")
def health():
    from src.diagnostics import health_check
    return health_check()


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
def api_agent_gate(
    request: Request,
    body: dict = Body(...),
    authorization: str | None = Header(default=None),
):
    """Pre-LLM relevance gate for chat widget."""
    from src.store import is_agent_banned, log_agent_gate_block, record_agent_abuse
    from src.tools.agent_gate import gate_message

    actor = _agent_actor(request, authorization)
    if is_agent_banned(actor):
        return JSONResponse(
            {"allowed": False, "score": 0.0, "reason": "banned", "response": "Chat suspended."},
            status_code=403,
        )

    text = str(body.get("message") or "")
    result = gate_message(text)
    if not result.allowed:
        log_agent_gate_block(text, result.score, result.reason)
        strikes = record_agent_abuse(actor, result.reason)
        if strikes >= 10:
            return JSONResponse(
                {"allowed": False, "score": result.score, "reason": "banned", "response": "Chat suspended."},
                status_code=403,
            )
    return {
        "allowed": result.allowed,
        "score": result.score,
        "reason": result.reason,
        "response": result.response,
    }


def _agent_actor(request: Request, authorization: str | None) -> str:
    from src.db.supabase_auth import user_from_token

    user = user_from_token(authorization)
    if user and user.get("id"):
        return str(user["id"])
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


@app.post("/api/agent/chat")
def api_agent_chat(
    request: Request,
    body: dict = Body(...),
    tier: str = Depends(get_user_tier),
    authorization: str | None = Header(default=None),
):
    """Compact-context desk chat — trading engine tone, max ~320 tokens."""
    from src.tools.agent_chat import chat

    text = str(body.get("message") or "")
    if not text.strip():
        raise HTTPException(400, "message required")
    actor = _agent_actor(request, authorization)
    return chat(text, tier=tier, actor_key=actor)


@app.post("/api/agent/generate")
def api_agent_generate(
    request: Request,
    body: dict = Body(default={}),
    authorization: str | None = Header(default=None),
    tier: str = Depends(get_user_tier),
):
    """VIP-only agent generation scaffold — master always allowed."""
    from datetime import datetime, timezone

    from src.db.supabase_auth import user_from_token
    from src.store import increment_agent_usage

    caps = tier_caps(tier)
    token = authorization or ""
    if not is_master(token) and not caps.get("can_generate_agents"):
        return JSONResponse({"error": "agent_generation_vip_only"}, status_code=403)
    scope = str(body.get("scope") or "watchlist")[:64]
    tickers = body.get("tickers") or []
    if not isinstance(tickers, list):
        tickers = []
    tickers = [str(t).upper()[:8] for t in tickers[:20]]

    user = user_from_token(authorization)
    email = str(user.get("email") or "anonymous").lower() if user else "anonymous"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated = increment_agent_usage(email, day)

    return {
        "status": "queued",
        "scope": scope,
        "tickers": tickers,
        "generated": generated,
        "message": "Agent generation request accepted. Outputs appear on your desk when the next pipeline completes.",
    }


@app.get("/api/agent/usage")
def api_agent_usage(
    date: str = Query(default="today"),
    tier: str = Depends(get_user_tier),
    authorization: str | None = Header(default=None),
):
    from datetime import datetime, timezone

    from src.db.supabase_auth import user_from_token
    from src.store import get_agent_usage

    user = user_from_token(authorization)
    email = str(user.get("email") or "anonymous").lower() if user else "anonymous"
    day = (
        datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if date == "today"
        else str(date)[:10]
    )
    count = get_agent_usage(email, day)
    limit = None if tier in ("vip", "master") else 1
    return {
        "generated": count,
        "limit": limit,
        "can_generate": limit is None or count < limit,
    }


@app.get("/api/stock/cassandra-target")
def api_stock_cassandra_target(
    crs: float = Query(..., ge=0, le=100),
    morningstar_fv: float = Query(..., gt=0),
    capex_score: float | None = Query(default=None, ge=0, le=1),
):
    from src.store import latest_score
    from src.tools.price_target import capex_score_from_score_dict, compute_cassandra_target

    score = latest_score()
    capex = capex_score if capex_score is not None else capex_score_from_score_dict(score)
    return compute_cassandra_target(morningstar_fv, crs, capex)


@app.post("/api/auth/login")
def auth_login(body: dict = Body(default={})):
    from src.db.supabase_auth import sign_in

    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")
    if not email or not password:
        raise HTTPException(400, "Email and password required")
    result = sign_in(email, password)
    if result.get("error"):
        code = 503 if result["error"] == "auth_not_configured" else 401
        return JSONResponse(result, status_code=code)
    return result


@app.post("/api/auth/signup")
def auth_signup(body: dict = Body(default={})):
    from src.db.supabase_auth import sign_up

    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")
    if not email or not password:
        raise HTTPException(400, "Email and password required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    result = sign_up(email, password)
    if result.get("error"):
        code = 503 if result["error"] == "auth_not_configured" else 400
        return JSONResponse(result, status_code=code)
    return result


@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)):
    from src.db.supabase_client import is_configured
    from src.db.supabase_auth import user_from_token

    if not is_configured():
        return {"auth_configured": False, "tier": "free"}
    user = user_from_token(authorization)
    if not user:
        raise HTTPException(401, "Not signed in")
    return {"auth_configured": True, **user}


@app.post("/api/auth/logout")
def auth_logout():
    """Clear client session — always 200."""
    return {"ok": True}


@app.get("/api/auth/oauth/{provider}")
def auth_oauth(provider: str, request: Request):
    from src.db.supabase_auth import get_oauth_url

    redirect_back = f"{request.base_url}api/auth/callback"
    try:
        url = get_oauth_url(provider, redirect_back)
    except RuntimeError:
        return JSONResponse({"error": "auth_not_configured"}, status_code=503)
    except ValueError:
        raise HTTPException(400, "Unsupported provider")
    return RedirectResponse(url)


@app.get("/api/auth/callback")
def auth_callback(
    request: Request,
    access_token: str | None = Query(default=None),
    refresh_token: str | None = Query(default=None),
):
    parts: list[str] = []
    if access_token:
        parts.append(f"access_token={quote_plus(access_token)}")
    if refresh_token:
        parts.append(f"refresh_token={quote_plus(refresh_token)}")
    hash_q = "#" + "&".join(parts) if parts else ""
    return RedirectResponse(f"/{hash_q}")


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Stripe checkout/subscription events → Supabase tier sync."""
    from src.db.supabase_auth import apply_subscription, find_user_id_by_email

    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Stripe webhook not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        import stripe

        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except ImportError as exc:
        raise HTTPException(503, "Install stripe package for webhook verification") from exc
    except Exception as exc:
        raise HTTPException(400, "Invalid Stripe signature") from exc

    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    def _is_cassandra_event(meta: dict) -> bool:
        line = str((meta or {}).get("product_line") or "").lower()
        return not line or line == "cassandra"

    def _normalize_tier(raw: str | None) -> str | None:
        if not raw:
            return None
        key = str(raw).lower()
        mapping = {
            "report": "report",
            "pro": "briefing",
            "briefing": "briefing",
            "api": "agent",
            "agent": "agent",
        }
        return mapping.get(key)

    def _tier_from_metadata(meta: dict) -> str | None:
        return _normalize_tier((meta or {}).get("tier") or (meta or {}).get("plan"))

    def _tier_from_price(price_id: str) -> str | None:
        mapping = {
            os.getenv("STRIPE_PRICE_REPORT", ""): "report",
            os.getenv("STRIPE_PRICE_PRO", ""): "briefing",
            os.getenv("STRIPE_PRICE_BRIEFING", ""): "briefing",
            os.getenv("STRIPE_PRICE_API", ""): "agent",
            os.getenv("STRIPE_PRICE_AGENT", ""): "agent",
        }
        return mapping.get(price_id or "")

    if etype in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
        meta = obj.get("metadata") or {}
        if not _is_cassandra_event(meta):
            return {"received": True, "skipped": "not_cassandra"}
        tier = _tier_from_metadata(meta)
        if not tier and obj.get("items", {}).get("data"):
            price_id = obj["items"]["data"][0].get("price", {}).get("id", "")
            tier = _tier_from_price(price_id)
        if not tier and obj.get("display_items"):
            price_id = obj["display_items"][0].get("price", {}).get("id", "")
            tier = _tier_from_price(price_id)
        email = obj.get("customer_email") or meta.get("email")
        user_id = meta.get("user_id") or meta.get("supabase_user_id")
        if not user_id and email:
            user_id = find_user_id_by_email(str(email))
        if user_id and tier:
            status = "active"
            if etype == "customer.subscription.updated" and obj.get("status") in ("canceled", "unpaid", "past_due"):
                status = str(obj.get("status"))
            apply_subscription(
                user_id=str(user_id),
                tier=tier,
                provider="stripe",
                external_id=str(obj.get("id") or obj.get("subscription") or ""),
                status=status,
            )
    elif etype == "customer.subscription.deleted":
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id") or meta.get("supabase_user_id")
        if user_id:
            apply_subscription(
                user_id=str(user_id),
                tier=str(meta.get("tier") or "report"),
                provider="stripe",
                external_id=str(obj.get("id") or ""),
                status="canceled",
            )
    return {"received": True}


@app.post("/api/digest/signup")
def digest_signup(body: dict = Body(...)):
    """Free daily digest — auto-confirmed at signup (no double-opt-in)."""
    from src.newsletter.resend_contacts import add_contact
    from src.store import count_confirmed_digest_subscribers, save_digest_subscriber

    email = str(body.get("email") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    source = str(body.get("source") or "newspaper")[:32]
    is_new, confirmed, unsub_token = save_digest_subscriber(email, source)
    if confirmed and unsub_token:
        add_contact(email, unsub_token, source=source)
    count = count_confirmed_digest_subscribers()
    return {
        "ok": True,
        "new": is_new,
        "confirmed": confirmed,
        "subscriber_count": count,
        "resend_synced": confirmed and bool(unsub_token),
        "message": (
            "You're on the free daily list. Check your inbox on the next trading-day edition."
            if is_new
            else "You're already on the free daily list."
        ),
    }


@app.get("/api/digest/confirm")
def digest_confirm(token: str = Query(..., min_length=8)):
    """Double opt-in confirm — returns 501 until DIGEST_DOUBLE_OPTIN=true."""
    import os

    from src.store import confirm_digest_subscriber

    if os.getenv("DIGEST_DOUBLE_OPTIN", "false").lower() != "true":
        raise HTTPException(501, "Double opt-in not enabled")
    if confirm_digest_subscriber(token):
        return {"ok": True, "confirmed": True}
    raise HTTPException(400, "Invalid or expired confirmation token")


_UNSUB_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Unsubscribed — Cassandra</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&display=swap" rel="stylesheet"/>
<style>body{{font-family:'DM Sans',sans-serif;max-width:480px;margin:4rem auto;padding:0 1.25rem;color:#1a1a1a;line-height:1.6;}}
h1{{font-size:1.5rem;font-weight:500;}}p{{color:#444;}}a{{color:#1a1a1a;}}</style></head>
<body><h1>{title}</h1><p>{body}</p><p><a href="/">← Back to desk</a></p></body></html>"""


@app.get("/unsubscribe")
@app.get("/api/digest/unsubscribe")
def digest_unsubscribe(token: str = Query(..., min_length=8)):
    from src.newsletter.resend_contacts import remove_contact
    from src.store import unsubscribe_digest

    email = unsubscribe_digest(token)
    if email:
        remove_contact(email)
        html = _UNSUB_HTML.format(
            title="Unsubscribed ✓",
            body="You will no longer receive the Cassandra free daily edition at this address.",
        )
        return HTMLResponse(html)
    html = _UNSUB_HTML.format(
        title="Link not found",
        body="This unsubscribe link is invalid or was already used.",
    )
    return HTMLResponse(html, status_code=400)


@app.get("/api/digest/subscribers")
def digest_subscribers(_: None = Depends(_require_pipeline_key)):
    """Ops visibility — confirmed subscribers only (PIPELINE_KEY gated)."""
    from src.store import count_confirmed_digest_subscribers, recent_digest_subscribers

    return {
        "count": count_confirmed_digest_subscribers(),
        "recent": recent_digest_subscribers(5),
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
            purpose="contact",
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


@app.get("/api/backtest")
def api_backtest(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    _: None = Depends(_require_pipeline_key),
):
    from src.backtest import run_backtest

    return run_backtest(start, end).model_dump()


@app.post("/api/newsletter/dispatch")
def newsletter_dispatch(
    body: dict = Body(default={}),
    _: None = Depends(_require_pipeline_key),
):
    """Internal batch dispatch — PIPELINE_KEY gated only."""
    from src.newsletter.send import dispatch_digest

    dry_run = bool(body.get("dry_run"))
    try:
        return dispatch_digest(dry_run=dry_run)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


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


@app.get("/api/quote/{symbol}")
def api_quote(symbol: str):
    from src.tools.movers import verified_quote

    q = verified_quote(symbol)
    if not q:
        raise HTTPException(404, "Quote unavailable")
    return q


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


@app.get("/api/ops/runs")
def ops_runs(
    request: Request,
    _: None = Depends(_require_ops),
):
    from src.store import get_run_history

    return {"runs": get_run_history(30)}


@app.get("/api/ops/run/{run_id}")
def ops_run_detail(
    run_id: str,
    request: Request,
    _: None = Depends(_require_ops),
):
    from src.store import get_run_detail

    detail = get_run_detail(run_id)
    if not detail:
        raise HTTPException(404, "Run not found")
    return detail


@app.get("/api/ops/run/latest")
def ops_run_latest():
    from src.store import get_run_history, get_run_detail

    runs = get_run_history(1)
    if not runs:
        return {"run": None, "agent_outputs": []}
    run_id = runs[0]["run_id"]
    detail = get_run_detail(run_id) or {}
    agents_file = ROOT / "knowledge" / "agents"
    latest = sorted(agents_file.glob("*.md"), reverse=True)
    outputs: list[str] = []
    if latest:
        text = latest[0].read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("## "):
                outputs.append(line.removeprefix("## ").strip())
    return {"run": detail, "agent_outputs": outputs[:12]}


@app.post("/api/ops/pipeline/trigger")
def ops_pipeline_trigger(
    request: Request,
    body: dict = Body(default={}),
    _: None = Depends(_require_ops),
):
    """Start orchestrator --run in background subprocess."""
    from datetime import datetime, timedelta, timezone

    from src.store import get_last_pipeline_completed_at

    last = get_last_pipeline_completed_at()
    if last and not body.get("force"):
        if datetime.now(timezone.utc) - last < timedelta(hours=2):
            raise HTTPException(
                409,
                detail={
                    "error": "recent_run",
                    "message": "Last pipeline run was less than 2 hours ago. Pass force:true to override.",
                    "last_completed_at": last.isoformat(),
                },
            )
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.orchestrator", "--run"],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )
    return {"status": "started", "run_id": None, "pid": proc.pid}


@app.post("/api/ops/newsletter/send")
def ops_newsletter_send(
    request: Request,
    _: None = Depends(_require_ops),
):
    from src.newsletter.send import dispatch_digest
    from src.store import get_run_history, latest_run_id, mark_newsletter_sent, was_newsletter_sent

    runs = get_run_history(1)
    if not runs:
        raise HTTPException(404, "No pipeline runs yet")
    latest = runs[0]
    run_id = latest["run_id"]
    latest_id = latest_run_id()
    if latest_id and run_id != latest_id:
        return JSONResponse({"error": "can_only_send_latest_edition"}, status_code=409)
    if latest_id and was_newsletter_sent(latest_id):
        return JSONResponse({"error": "already_sent_this_edition"}, status_code=409)
    if was_newsletter_sent(run_id):
        return JSONResponse({"error": "already_sent_this_edition"}, status_code=409)
    try:
        result = dispatch_digest(dry_run=False)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    mark_newsletter_sent(run_id)
    return {"sent": result.get("sent", 0), "failed": result.get("failed", 0), "run_id": run_id}


@app.get("/api/ops/reports")
def ops_reports_list(
    request: Request,
    date: str = Query(..., description="YYYY-MM-DD"),
    edition: str = Query(default="morning", description="morning or evening"),
    _: None = Depends(_require_ops),
):
    from src.store import list_report_markdown

    edition = edition.lower()
    if edition not in ("morning", "evening"):
        raise HTTPException(400, "edition must be morning or evening")
    files = list_report_markdown(date=date, edition=edition)
    return {"date": date, "edition": edition, "files": files}


@app.get("/api/ops/reports/{filename}")
def ops_reports_get(
    filename: str,
    request: Request,
    _: None = Depends(_require_ops),
):
    from src.store import read_report_markdown

    content = read_report_markdown(filename)
    if content is None:
        raise HTTPException(404, "Report file not found")
    return {"filename": Path(filename).name, "markdown": content}
