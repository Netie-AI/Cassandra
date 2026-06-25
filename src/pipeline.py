"""
pipeline.py — collect live metrics, score, persist. No LLM (Phase 2–3 bridge).

Run: python -m src.pipeline
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import yaml

from . import scoring, phase
from .config import load_settings, load_weights
from .schemas import DailyScore, FactorBreakdown, MomentumState, Phase
from .store import fragility_history, history_lookup, latest_score, save_metrics, save_report_graph, save_score
from .tools._env import load_env

load_env()
ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "settings.yaml"


def _basket(cfg: dict) -> list[str]:
    b = cfg.get("basket", {})
    return list(b.get("semis", [])) + list(b.get("hyperscalers", []))[:5]


def collect_metrics(cfg: dict) -> list:
    from .tools import coingecko, finra, fred, yfinance_client

    metrics = []
    metrics.extend(fred.fetch())
    metrics.extend(finra.fetch())
    metrics.extend(yfinance_client.fetch_breadth(_basket(cfg)))
    if cfg.get("features", {}).get("enable_crypto_crossread", True):
        metrics.extend(coingecko.fetch())

    try:
        from .tools import alphavantage
        _, mrs = alphavantage.fetch_news(_basket(cfg)[:3], limit=10)
        metrics.extend(mrs)
    except Exception:
        pass

    try:
        from .tools import fmp
        from .tools._env import get_key
        if get_key("FMP_API_KEY"):
            metrics.extend(fmp.fetch_all_whale(_basket(cfg)))
    except Exception:
        pass

    return metrics


# Metrics already on 0–1 scale (LLM grader output) — skip z-score when history sparse
PRE_NORMALIZED = frozenset({"capex_cut_nlp", "supply_tells"})


def normalize_metrics(metrics: list) -> tuple[dict, float, float]:
    by_factor: dict[str, dict] = {k: {} for k in "LVSBC"}
    present = total = 0
    fresh_terms = []
    now = dt.datetime.now(dt.timezone.utc)

    for m in metrics:
        total += 1
        if m.raw_value is None:
            by_factor[m.factor][m.name] = None
            continue
        present += 1
        if m.name in PRE_NORMALIZED:
            n = max(0.0, min(1.0, float(m.raw_value)))
        else:
            hist = history_lookup(m.name)
            if m.use_percentile:
                n = scoring.normalize_percentile(
                    m.raw_value, hist, int(m.direction), m.hard_threshold)
            else:
                n = scoring.normalize_zscore(m.raw_value, hist, int(m.direction))
        by_factor[m.factor][m.name] = n
        asof = m.asof if m.asof.tzinfo else m.asof.replace(tzinfo=dt.timezone.utc)
        age_days = max((now - asof).total_seconds() / 86400, 0)
        fresh_terms.append(2.718 ** (-age_days / 20.0))

    freshness = sum(fresh_terms) / len(fresh_terms) if fresh_terms else 0.5
    coverage = present / total if total else 0.0
    return by_factor, freshness, coverage


def run_pipeline() -> DailyScore:
    cfg = load_settings(CFG) if CFG.exists() else {}
    weights = load_weights(CFG)
    metrics = collect_metrics(cfg)
    normalized, freshness, coverage = normalize_metrics(metrics)
    result = scoring.compute_crs(normalized, freshness=freshness, coverage=coverage, weights=weights)

    f_hist = fragility_history(9) + [result.fragility]
    df_dt, mom_state = scoring.fragility_momentum(f_hist)

    ph = phase.PhaseResult(phase="distribution_range", confidence=0.5, evidence=["pipeline default"])
    try:
        from .tools import yfinance_client
        path = yfinance_client.get_index_ohlcv_path("^GSPC")
        if path:
            ohlcv = pd.read_csv(path, index_col=0, parse_dates=True)
            ohlcv.columns = [c.lower() for c in ohlcv.columns]
            ph = phase.classify(ohlcv)
    except Exception:
        pass

    score = DailyScore(
        asof=dt.date.today(),
        crs=result.crs, band_halfwidth=result.band_halfwidth, confidence=result.confidence,
        fragility=result.fragility, trigger=result.trigger,
        factors=FactorBreakdown(**result.factors),
        momentum_state=MomentumState(mom_state), df_dt=round(df_dt, 5),
        phase=Phase(ph.phase), phase_confidence=ph.confidence,
        band_label=result.band, coverage=result.coverage,
    )
    save_score(score, extra={"metric_count": len(metrics), "coverage": coverage})
    save_report_graph(
        score.asof,
        {
            "asof": score.asof.isoformat(),
            "crs": score.crs,
            "band": score.band_label,
            "fragility": score.fragility,
            "trigger": score.trigger,
            "phase": score.phase.value,
            "phase_confidence": score.phase_confidence,
            "coverage": score.coverage,
        },
        sections={
            "headline": f"Market desk edition for {score.asof.isoformat()}",
            "sub_headline": "Automated pipeline snapshot",
            "col1_html": "",
            "col2_html": "",
            "col3_html": "",
        },
        highlights={"analog_date": "March 14, 2000", "analog_news": [], "today_news": []},
    )
    save_metrics(score.asof, metrics)

    try:
        from .tools.cf_publish import publish_score
        publish_score(score)
    except Exception:
        pass

    return score


if __name__ == "__main__":
    s = run_pipeline()
    print(f"CRS={s.crs} band={s.band_label} F={s.fragility} T={s.trigger} coverage={s.coverage}")
