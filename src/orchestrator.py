"""
orchestrator.py — the daily cycle.

Flow:
  1. calendar gate (unless --run force)
  2. dispatch 5 subagents in parallel → typed *Read bundles
  3. normalize metrics → compute_crs (pure Python) + classify phase
  4. orchestrator meta-call (Opus) → publish / escalate decision
  5. report narrative (Gemini) → persist + publish

The LLM NEVER computes the score.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from . import scoring, phase
from .calendar_guard import should_run as calendar_should_run
from .config import load_settings, load_weights
from .pipeline import normalize_metrics
from .schemas import (
    DailyScore,
    Direction,
    FactorBreakdown,
    FlowRead,
    FragilityRead,
    MomentumState,
    NewsRead,
    Phase,
    StructureRead,
    WhaleRead,
)
from .store import fragility_history, save_metrics, save_newspaper_body, save_report_graph, save_score
from .tools._env import load_env

load_env()

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "settings.yaml"

ORCHESTRATOR_SYSTEM = """\
You are a pipeline supervisor. You receive a coverage report and CRS score.
Return ONLY JSON. No prose.

Inputs you receive:
- crs: float
- coverage: float (0-1, fraction of 5 agents that returned data)
- capex_fire: bool (any snippet scored >= 0.80)
- phase: str

Output schema:
{
  "publish": bool,
  "escalate_human": bool,
  "escalate_reason": str|null,
  "confidence_override": float|null
}

Rules:
- coverage < 0.4 → publish=false, escalate_human=true
- capex_fire=true AND crs > 70 → escalate_human=true, reason="CAPEX FIRE + HIGH CRS"
- Otherwise → publish=true, escalate_human=false
"""


def _basket(cfg: dict) -> list[str]:
    b = cfg.get("basket", {})
    return list(b.get("semis", [])) + list(b.get("hyperscalers", []))[:5]


def _metric_val(metrics: list, name: str) -> float | None:
    for m in metrics:
        if m.name == name:
            return m.raw_value
    return None


async def _run_sync(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


async def run_news_digestor(cfg: dict) -> NewsRead | None:
    def _fetch() -> NewsRead:
        import json

        from .tools import alphavantage
        from .tools._llm import llm_extract
        from .tools.capex_nlp import score_capex_cut
        from .tools.metric_map import merge_metric, metric
        from .tools.subagent_prompts import NEWS_FALLBACK, NEWS_SYSTEM

        basket = _basket(cfg)
        _, metrics = alphavantage.fetch_news(basket[:3], limit=10)
        hits: list = []
        try:
            from .tools import tavily
            for sym in basket[:3]:
                hits.extend(tavily.capex_cut_search(sym))
        except Exception:
            pass

        raw_parts = [getattr(h, "content", "") or "" for h in hits[:10]]
        raw_text = "\n---\n".join(p for p in raw_parts if p.strip())
        extracted = llm_extract(NEWS_SYSTEM, raw_text[:4000] or "no news", NEWS_FALLBACK)

        snippets = extracted.get("capex_cut_snippets") or []
        scores = []
        for s in snippets[:3]:
            if isinstance(s, dict) and s.get("text"):
                scores.append(score_capex_cut(s["text"]))
        if not scores and hits:
            scores = [
                score_capex_cut(getattr(h, "content", "") or "")
                for h in hits[:3]
            ]
        capex_score = max(scores) if scores else 0.0

        supply = extracted.get("supply_tell")
        metrics = list(metrics)
        if supply is not None:
            metrics = merge_metric(
                metrics, "supply_tells", "C", supply, "llm+news",
            )
        metrics.append(metric(
            "capex_cut_nlp", "C",
            capex_score if capex_score > 0 else None,
            "tavily+capex_nlp",
            note="LLM-graded hyperscaler capex-cut language",
        ))

        return NewsRead(
            items=[],
            capex_cut_signal=min(1.0, max(0.0, capex_score)),
            supply_tell_signal=float(supply) if supply is not None else 0.0,
            metrics=metrics,
        )

    return await _run_sync(_fetch)


async def run_market_structure(cfg: dict) -> StructureRead | None:
    def _fetch() -> StructureRead:
        import json

        from .tools import yfinance_client
        from .tools._llm import llm_extract, summarize_metrics
        from .tools.metric_map import merge_metric
        from .tools.movers import fetch_watchlist_movers
        from .tools.subagent_prompts import STRUCTURE_FALLBACK, STRUCTURE_SYSTEM

        metrics = yfinance_client.fetch_breadth(_basket(cfg))
        path = yfinance_client.get_index_ohlcv_path("^GSPC") or ""
        live_movers = fetch_watchlist_movers()
        payload = json.dumps({"raw_metrics": summarize_metrics(metrics)})
        extracted = llm_extract(STRUCTURE_SYSTEM, payload, STRUCTURE_FALLBACK)

        pct = _metric_val(metrics, "pct_above_200dma") or extracted.get("pct_above_200dma")
        if pct is not None:
            metrics = merge_metric(
                list(metrics), "pct_above_200dma", "B", pct, "yfinance+llm",
                direction=Direction.BULLISH_HIGH,
            )

        return StructureRead(
            ohlcv_csv_path=path,
            pct_above_200dma=pct,
            new_highs=extracted.get("new_highs_52w"),
            new_lows=extracted.get("new_lows_52w"),
            index_breadth_divergence=_metric_val(metrics, "divergence"),
            ad_line_slope=extracted.get("advance_decline_ratio"),
            live_movers=live_movers,
            metrics=metrics,
        )

    return await _run_sync(_fetch)


async def run_derivatives_flow(cfg: dict) -> FlowRead | None:
    def _fetch() -> FlowRead:
        import json

        from .tools._env import get_key
        from .tools._llm import llm_extract, summarize_metrics
        from .tools.metric_map import merge_metric
        from .tools.subagent_prompts import FLOW_FALLBACK, FLOW_SYSTEM

        metrics: list = []
        basket = _basket(cfg)
        try:
            from .tools import polygon, unusual_whales
            if get_key("POLYGON_API_KEY") and basket:
                metrics.extend(polygon.fetch_options_metrics(basket[0]))
            if get_key("UNUSUAL_WHALES_API_KEY"):
                metrics.extend(unusual_whales.fetch_flow_metrics(basket))
                metrics.extend(unusual_whales.fetch_market_summary())
        except Exception:
            pass

        extracted = llm_extract(
            FLOW_SYSTEM,
            json.dumps({"raw_metrics": summarize_metrics(metrics)}),
            FLOW_FALLBACK,
        )

        def _pick(name: str, llm_key: str, factor: str = "S") -> list:
            raw = _metric_val(metrics, name) or extracted.get(llm_key)
            if raw is None:
                return metrics
            return merge_metric(list(metrics), name, factor, raw, "flow+llm")

        metrics = _pick("put_call_inv", "put_call_ratio")
        metrics = _pick("iv_skew", "iv_skew_25d")
        metrics = _pick("gamma_exposure", "gamma_exposure")
        if _metric_val(metrics, "gamma_exposure") is None and extracted.get("gamma_exposure") is not None:
            metrics = merge_metric(metrics, "uw_gex_total", "S", extracted["gamma_exposure"], "flow+llm")
        if extracted.get("retail_call_streak") is not None:
            metrics = merge_metric(metrics, "retail_call_streak", "S", extracted["retail_call_streak"], "flow+llm")

        return FlowRead(
            put_call_ratio=_metric_val(metrics, "put_call_inv") or extracted.get("put_call_ratio"),
            iv_skew_25d=_metric_val(metrics, "iv_skew") or extracted.get("iv_skew_25d"),
            iv_term_structure=_metric_val(metrics, "iv_term_structure"),
            gamma_exposure=_metric_val(metrics, "gamma_exposure") or _metric_val(metrics, "uw_gex_total"),
            retail_call_buying_streak=_metric_val(metrics, "retail_call_streak") or extracted.get("retail_call_streak"),
            metrics=metrics,
        )

    return await _run_sync(_fetch)


async def run_whale_smart_money(cfg: dict) -> WhaleRead | None:
    def _fetch() -> WhaleRead:
        import json

        from .tools import fmp
        from .tools._env import get_key
        from .tools._llm import llm_extract, summarize_metrics
        from .tools.metric_map import merge_metric
        from .tools.subagent_prompts import WHALE_FALLBACK, WHALE_SYSTEM

        metrics: list = []
        basket = _basket(cfg)
        if get_key("FMP_API_KEY"):
            metrics.extend(fmp.fetch_all_whale(basket))
        try:
            from .tools import unusual_whales
            if get_key("UNUSUAL_WHALES_API_KEY"):
                metrics.extend(unusual_whales.fetch_darkpool_metrics(basket))
        except Exception:
            pass

        extracted = llm_extract(
            WHALE_SYSTEM,
            json.dumps({"raw_metrics": summarize_metrics(metrics)}),
            WHALE_FALLBACK,
        )

        insider = _metric_val(metrics, "insider_sell_buy_ratio") or extracted.get("insider_sell_buy_ratio")
        if insider is not None:
            metrics = merge_metric(metrics, "insider_sell_buy_ratio", "S", insider, "whale+llm")
        dark = _metric_val(metrics, "uw_darkpool_short") or extracted.get("darkpool_short_volume_ratio")
        if dark is not None:
            metrics = merge_metric(metrics, "uw_darkpool_short", "S", dark, "whale+llm")

        return WhaleRead(
            insider_sell_buy_ratio=insider,
            inst_13f_net_flow=extracted.get("inst_13f_net_flow"),
            darkpool_short_volume_ratio=dark,
            metrics=metrics,
        )

    return await _run_sync(_fetch)


async def run_fundamentals_fragility(cfg: dict) -> FragilityRead | None:
    def _fetch() -> FragilityRead:
        import json

        from .tools import finra, fred, fmp
        from .tools._env import get_key
        from .tools._llm import llm_extract, summarize_metrics
        from .tools.metric_map import merge_metric
        from .tools.subagent_prompts import FRAGILITY_FALLBACK, FRAGILITY_SYSTEM

        metrics: list = []
        metrics.extend(fred.fetch())
        metrics.extend(finra.fetch())
        if get_key("FMP_API_KEY"):
            try:
                metrics.extend(fmp.fetch_capex_rev_gap(_basket(cfg)))
            except Exception:
                pass

        extracted = llm_extract(
            FRAGILITY_SYSTEM,
            json.dumps({"raw_metrics": summarize_metrics(metrics)}),
            FRAGILITY_FALLBACK,
        )

        def _sync(name: str, key: str, factor: str) -> None:
            nonlocal metrics
            raw = _metric_val(metrics, name) or extracted.get(key)
            if raw is not None and _metric_val(metrics, name) is None:
                metrics = merge_metric(metrics, name, factor, raw, "fragility+llm")

        _sync("margin_debt_yoy", "margin_debt_yoy", "L")
        _sync("credit_spread_inv", "credit_spread_inv", "L")
        _sync("mktcap_gdp", "mktcap_to_gdp", "V")
        _sync("capex_rev_gap_slope", "capex_rev_gap_slope", "C")
        _sync("net_liquidity", "net_liquidity", "C")

        return FragilityRead(
            margin_debt_yoy=_metric_val(metrics, "margin_debt_yoy"),
            margin_to_mktcap=_metric_val(metrics, "margin_to_mktcap"),
            credit_spread=_metric_val(metrics, "credit_spread_inv"),
            cohort_fwd_ps=None,
            mktcap_to_gdp=_metric_val(metrics, "mktcap_gdp"),
            top10_concentration=None,
            equity_risk_premium=None,
            debt_funded_capex=None,
            fed_hike_odds=None,
            capex_rev_gap_slope=_metric_val(metrics, "capex_rev_gap_slope"),
            net_liquidity=_metric_val(metrics, "net_liquidity"),
            metrics=metrics,
        )

    return await _run_sync(_fetch)


async def dispatch_subagents(cfg: dict) -> list[Any]:
    """Run all 5 subagents in parallel; failures become None."""
    results = await asyncio.gather(
        run_news_digestor(cfg),
        run_market_structure(cfg),
        run_derivatives_flow(cfg),
        run_whale_smart_money(cfg),
        run_fundamentals_fragility(cfg),
        return_exceptions=True,
    )
    out: list[Any] = []
    for r in results:
        out.append(None if isinstance(r, Exception) else r)
    return out


def subagent_coverage(bundles: list[Any]) -> float:
    return sum(1 for b in bundles if b is not None) / 5.0


def collect_metrics(bundles: list[Any]) -> list:
    metrics: list = []
    for b in bundles:
        if b is not None:
            metrics.extend(getattr(b, "metrics", []))
    return metrics


def capex_fire(bundles: list[Any]) -> bool:
    for b in bundles:
        if isinstance(b, NewsRead) and b.capex_cut_signal >= 0.80:
            return True
    return False


def _decision_rules(crs: float, coverage: float, fire: bool) -> dict[str, Any]:
    if coverage < 0.4:
        return {
            "publish": False,
            "escalate_human": True,
            "escalate_reason": "coverage below 0.4",
            "confidence_override": None,
        }
    if fire and crs > 70:
        return {
            "publish": True,
            "escalate_human": True,
            "escalate_reason": "CAPEX FIRE + HIGH CRS",
            "confidence_override": None,
        }
    return {
        "publish": True,
        "escalate_human": False,
        "escalate_reason": None,
        "confidence_override": None,
    }


def orchestrator_decide(
    score: DailyScore, agent_cov: float, fire: bool,
) -> dict[str, Any]:
    """Meta supervisor — deterministic rules first; Opus validates if key present."""
    payload = {
        "crs": score.crs,
        "coverage": agent_cov,
        "capex_fire": fire,
        "phase": score.phase.value,
    }
    fallback = _decision_rules(score.crs, agent_cov, fire)

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_ORCHESTRATOR_MODEL", "anthropic/claude-opus-4-8")
    if not api_key:
        return fallback

    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "max_tokens": 120,
                "temperature": 0.0,
                "messages": [
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=45,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return fallback


def build_highlights(bundles: list[Any]) -> dict[str, Any]:
    """Ranked news for newspaper analog vs today panels."""
    today: list[dict[str, str]] = []
    news = next((b for b in bundles if isinstance(b, NewsRead)), None)
    if news:
        for m in getattr(news, "metrics", []):
            if m.raw_value is not None and m.source:
                today.append({
                    "title": m.name.replace("_", " "),
                    "source": m.source,
                    "asof": m.asof.date().isoformat() if m.asof else "",
                    "weight": round(float(m.raw_value), 2),
                })
        today.sort(key=lambda x: x.get("weight", 0), reverse=True)
    analog_news = [
        {"title": "Cisco warns on enterprise spending", "source": "Reuters", "asof": "2000-03-14"},
        {"title": "NASDAQ breadth narrows to mega-cap leaders", "source": "WSJ", "asof": "2000-03-13"},
        {"title": "Margin debt hits cycle high", "source": "FINRA", "asof": "2000-03-01"},
    ]
    return {
        "analog_date": "March 14, 2000",
        "analog_news": analog_news,
        "today_news": today[:5],
    }


async def run_cycle(cfg: dict, *, force: bool = False) -> DailyScore | None:
    if not force and calendar_should_run() is None:
        return None

    weights = load_weights(CONFIG)
    bundles = await dispatch_subagents(cfg)
    agent_cov = subagent_coverage(bundles)
    metrics = collect_metrics(bundles)

    normalized, freshness, metric_cov = normalize_metrics(metrics)
    coverage = agent_cov if agent_cov > 0 else metric_cov
    result = scoring.compute_crs(
        normalized, freshness=freshness, coverage=coverage, weights=weights,
    )

    f_hist = fragility_history(9) + [result.fragility]
    df_dt, mom_state = scoring.fragility_momentum(f_hist)

    ph = phase.PhaseResult(phase="distribution_range", confidence=0.5, evidence=["orchestrator default"])
    structure = next((b for b in bundles if isinstance(b, StructureRead)), None)
    if structure and structure.ohlcv_csv_path and Path(structure.ohlcv_csv_path).exists():
        try:
            ohlcv = pd.read_csv(structure.ohlcv_csv_path, index_col=0, parse_dates=True)
            ohlcv.columns = [c.lower() for c in ohlcv.columns]
            ph = phase.classify(ohlcv)
        except Exception:
            pass

    score = DailyScore(
        asof=dt.date.today(),
        crs=result.crs,
        band_halfwidth=result.band_halfwidth,
        confidence=result.confidence,
        fragility=result.fragility,
        trigger=result.trigger,
        factors=FactorBreakdown(**result.factors),
        momentum_state=MomentumState(mom_state),
        df_dt=round(df_dt, 5),
        phase=Phase(ph.phase),
        phase_confidence=ph.confidence,
        band_label=result.band,
        coverage=coverage,
    )

    fire = capex_fire(bundles)
    decision = orchestrator_decide(score, agent_cov, fire)

    if decision.get("confidence_override") is not None:
        score = score.model_copy(update={"confidence": float(decision["confidence_override"])})

    from . import report

    score_dict = score.model_dump(mode="json")
    score_dict["band"] = score.band_label
    sections = report.generate_report_sections(score_dict)
    i18n = report.generate_report_multilingual(score_dict)

    def _persist_body(lang: str, block: dict) -> None:
        save_newspaper_body(
            score.asof,
            lang,
            block.get("col1_html") or "",
            block.get("col2_html") or "",
            block.get("col3_html") or "",
        )

    _persist_body("en", sections)
    for lang in ("zh", "ms"):
        if i18n.get(lang):
            _persist_body(lang, i18n[lang])

    highlights = build_highlights(bundles)
    save_score(score, extra={
        "orchestrator": decision,
        "agent_coverage": agent_cov,
        "report_headline": sections.get("headline", ""),
        **highlights,
    })
    save_report_graph(
        score.asof,
        score_dict,
        sections=sections,
        highlights=highlights,
        i18n=i18n,
    )
    save_metrics(score.asof, metrics)

    if decision.get("publish", True):
        try:
            from .tools.cf_publish import publish_score
            publish_score(score)
        except Exception:
            pass

    return score


def load_cfg() -> dict:
    return load_settings(CONFIG) if CONFIG.exists() else {}


def main():
    p = argparse.ArgumentParser(description="CASSANDRA daily crash-risk research cycle")
    p.add_argument("--run", action="store_true", help="run one cycle now (bypasses calendar gate)")
    p.add_argument("--schedule", action="store_true", help="start the daily cron")
    p.add_argument("--backtest", action="store_true", help="replay historical fixtures")
    args = p.parse_args()
    cfg = load_cfg()

    if args.run:
        score = asyncio.run(run_cycle(cfg, force=True))
        if score is None:
            print('{"skipped": true, "reason": "calendar gate"}')
        else:
            print(score.model_dump_json(indent=2))
    elif args.schedule:
        from apscheduler.schedulers.blocking import BlockingScheduler

        sched = BlockingScheduler(timezone="UTC")
        for hh, mm in [(4, 0), (13, 0), (16, 0)]:
            sched.add_job(
                lambda c=cfg: asyncio.run(run_cycle(c)),
                "cron",
                hour=hh,
                minute=mm,
            )
        print("scheduled 3× daily at 04:00 / 13:00 / 16:00 UTC")
        sched.start()
    elif args.backtest:
        print("WIRE: replay store/evidence/* through scoring to calibrate weights (SPEC §10)")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
