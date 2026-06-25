---
name: news-digestor
description: >-
  Build or test the NEWS DIGESTOR subagent (NewsRead). Use for Phase 1 news
  clients, Phase 4 multi-region pipeline, capex-cut NLP, and supply-tell signals.
---

# News Digestor subagent

Prompt section: `agents/subagents.md` §1. Model: `claude-sonnet-4-6`. Returns: `NewsRead`.

## Mandate

Pull macro + sector news. Tag items (`fed|capex|supply|geo|other`), severity 0–1. Produce:

- `capex_cut_signal` 0→1 — **Lehman-moment detector**. Grade conservatively.
- `supply_tell_signal` 0→1 — supply catching demand tells.

## Tools to wire

- `src/tools/alphavantage.py` (news+sentiment)
- `src/tools/fmp.py` (earnings transcripts)
- Web search (Tavily/Serper) + fetch for primary sources

## Phase 4 extensions

Per `docs/NEWS_PIPELINE_SPEC.md`: Korea + China sources, translation (keep original + translation), 3× daily via `calendar_guard`, recent window only.

## Rules

- Paraphrase — never reproduce copyrighted text verbatim
- Distinguish guidance cuts from hedging
- Failed pulls → `raw_value=None` + note

## Test in isolation

Background agent task: implement client → run standalone → return sample `NewsRead` JSON matching `src/schemas.py`.
