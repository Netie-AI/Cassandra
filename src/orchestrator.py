"""
orchestrator.py — the daily cycle. Skeleton with explicit wiring points marked `# WIRE:`.

Flow (see ARCHITECTURE.md):
  1. load config + yesterday's score
  2. dispatch 5 subagents in parallel  -> typed *Read bundles
  3. normalize metrics (§2) -> compute_crs (§5) + classify phase (parallel)
  4. orchestrator pass-2 (Opus) -> written thesis
  5. persist DailyScore + write report markdown

The LLM NEVER computes the score. Subagents fetch+normalize; scoring.py does the arithmetic; the
orchestrator LLM only researches and explains.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
from pathlib import Path

import pandas as pd
import yaml

from . import scoring, phase
from .schemas import (DailyScore, FactorBreakdown, MomentumState, Phase)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "settings.yaml"
STORE = ROOT / "store"


# --------------------------------------------------------------------------- #
# Subagent dispatch — each returns its typed bundle.
# WIRE: implement each as an LLM call (claude-sonnet-4-6) using agents/subagents.md
#       + the tools/<source>.py API clients. The prompt instructs the model to
#       return JSON matching the schema; parse into the pydantic type.
# --------------------------------------------------------------------------- #
async def run_news_digestor(cfg) -> "NewsRead": ...        # WIRE
async def run_market_structure(cfg) -> "StructureRead": ...# WIRE
async def run_derivatives_flow(cfg) -> "FlowRead": ...     # WIRE
async def run_whale_smart_money(cfg) -> "WhaleRead": ...   # WIRE
async def run_fundamentals_fragility(cfg) -> "FragilityRead": ...  # WIRE


async def dispatch_subagents(cfg):
    return await asyncio.gather(
        run_news_digestor(cfg),
        run_market_structure(cfg),
        run_derivatives_flow(cfg),
        run_whale_smart_money(cfg),
        run_fundamentals_fragility(cfg),
    )


# --------------------------------------------------------------------------- #
# Normalization: turn the subagents' MetricReadings into {factor: {name: n_i}}
# Pulls each metric's history from the store to z-score / percentile it (§2).
# --------------------------------------------------------------------------- #
def normalize_all(bundles, history_lookup) -> tuple[dict, float, float]:
    """
    history_lookup(name) -> list[float] of prior raw values for that metric.
    Returns (normalized_by_factor, freshness, coverage).
    """
    by_factor: dict[str, dict[str, float | None]] = {k: {} for k in "LVSBC"}
    present = total = 0
    fresh_terms = []
    now = dt.datetime.utcnow()

    for bundle in bundles:
        for m in getattr(bundle, "metrics", []):
            total += 1
            if m.raw_value is None:
                by_factor[m.factor][m.name] = None
                continue
            present += 1
            hist = history_lookup(m.name)
            if m.use_percentile:
                n = scoring.normalize_percentile(m.raw_value, hist, int(m.direction), m.hard_threshold)
            else:
                n = scoring.normalize_zscore(m.raw_value, hist, int(m.direction))
            by_factor[m.factor][m.name] = n
            age_days = max((now - m.asof).total_seconds() / 86400, 0)
            fresh_terms.append(2.718 ** (-age_days / 20.0))   # τ=20d

    freshness = sum(fresh_terms) / len(fresh_terms) if fresh_terms else 0.5
    coverage = present / total if total else 0.0
    return by_factor, freshness, coverage


# --------------------------------------------------------------------------- #
# One full cycle
# --------------------------------------------------------------------------- #
async def run_cycle(cfg) -> DailyScore:
    bundles = await dispatch_subagents(cfg)

    # WIRE: history_lookup reads prior raw metric values from store/scores.sqlite
    def history_lookup(name: str) -> list[float]:
        return []   # WIRE: SELECT raw_value FROM metric_history WHERE name=?

    normalized, freshness, coverage = normalize_all(bundles, history_lookup)
    result = scoring.compute_crs(normalized, freshness=freshness, coverage=coverage)

    # Fragility momentum (§6): needs prior Fragility values from the store.
    f_hist = []  # WIRE: SELECT fragility FROM scores ORDER BY asof DESC LIMIT 10
    f_hist = list(reversed(f_hist)) + [result.fragility]
    df_dt, mom_state = scoring.fragility_momentum(f_hist)

    # Phase classifier (parallel conceptually; cheap enough to run inline).
    structure = next(b for b in bundles if hasattr(b, "ohlcv_csv_path"))
    ohlcv = pd.read_csv(structure.ohlcv_csv_path)   # WIRE: the StructureRead provides this path
    ph = phase.classify(ohlcv)

    score = DailyScore(
        asof=dt.date.today(),
        crs=result.crs, band_halfwidth=result.band_halfwidth, confidence=result.confidence,
        fragility=result.fragility, trigger=result.trigger,
        factors=FactorBreakdown(**result.factors),
        momentum_state=MomentumState(mom_state), df_dt=round(df_dt, 5),
        phase=Phase(ph.phase), phase_confidence=ph.confidence,
        band_label=result.band, coverage=result.coverage,
    )

    # WIRE: persist score + raw metric history + evidence bundles to the store.
    # WIRE: orchestrator pass-2 — feed `score` + bundles + agents/orchestrator.md to claude-opus-4-8
    #       to author DailyReport (headline, what_changed, firing/warning/watch, whos_next,
    #       what_would_change_my_mind, timing_caveat). Render markdown via report.py.
    return score


# --------------------------------------------------------------------------- #
# Entrypoints
# --------------------------------------------------------------------------- #
def load_cfg():
    return yaml.safe_load(CONFIG.read_text()) if CONFIG.exists() else {}


def main():
    p = argparse.ArgumentParser(description="CASSANDRA daily crash-risk research cycle")
    p.add_argument("--run", action="store_true", help="run one cycle now ('start')")
    p.add_argument("--schedule", action="store_true", help="start the daily cron")
    p.add_argument("--backtest", action="store_true", help="replay historical fixtures")
    args = p.parse_args()
    cfg = load_cfg()

    if args.run:
        score = asyncio.run(run_cycle(cfg))
        print(score.model_dump_json(indent=2))
    elif args.schedule:
        from apscheduler.schedulers.blocking import BlockingScheduler   # WIRE
        sched = BlockingScheduler(timezone=cfg.get("timezone", "Asia/Kuala_Lumpur"))
        hh, mm = map(int, cfg.get("run_time", "07:30").split(":"))
        sched.add_job(lambda: asyncio.run(run_cycle(cfg)), "cron", hour=hh, minute=mm)
        print(f"scheduled daily run at {hh:02d}:{mm:02d}")
        sched.start()
    elif args.backtest:
        print("WIRE: replay store/evidence/* through scoring to calibrate weights (SPEC §10)")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
