# NEWS_PIPELINE_SPEC

The upgraded News Digestor: multi-region, translated, scheduled to trading days only, and feeding the
two trigger signals the score depends on.

## Sources by region

- **English (primary):** Alpha Vantage news+sentiment, FMP earnings transcripts, a search API
  (Tavily/Serper), plus direct fetch of primary sources (company filings, Fed statements, exchange
  notices).
- **Korea:** Naver Finance, Daum Finance, ET News / MoneyToday for memory/semis (SK Hynix, Samsung).
  Asia trades and reacts first — these are leading tells for the memory complex.
- **China:** Eastmoney, Sina Finance, Caixin for supply-chain and demand signals.

**Legal / access reality:** prefer official APIs. Where you must scrape, respect `robots.txt` and each
site's ToS, rate-limit politely, and cache. Some Chinese sources are access-restricted and may need a
licensed data vendor; note coverage gaps rather than pretending completeness. Honor the deployment
network allowlist.

## Translation

Non-English items: translate to English (LLM translation, or DeepL API for volume) **before** analysis.
Always retain `{original_text, translation, source_url, language}` so the UI can show the source and a
reviewer can check the translation. Never analyze a machine translation without keeping the original.

## Schedule — 3× per trading day, calendar-gated

Driven by `calendar_guard.should_run()`. Runs **only on NYSE trading days** (year-aware holidays):
- **12:00 local (UTC+8) — ASIA_PM:** Korea/China/Asia sentiment has settled. The day's first read.
- **21:00 local — PRE_OPEN:** prep before the US open; fold in US pre-market + overnight wires.
- **00:00 local — OVERNIGHT:** wrap; capture late US session + after-hours earnings reactions.

Pull only the recent window (`calendar_guard.recent_window`, default 5 sessions). The system always
knows today's date and the current year's holiday set.

## What the digestor emits

For each item: own-words summary (no verbatim copying), tag (`fed|capex|supply|geo|other`), severity
0–1, source + asof + URL. Plus the two graded trigger signals the score consumes:

- **`capex_cut_signal` (0→1)** — the Lehman-moment detector and the single most important output.
  Grade from earnings-call / news language: `0` no cut talk; `~0.5` hedged ("optimizing spend,"
  "disciplined investment"); `0.85+` an explicit forward-capex guidance cut. Grade **conservatively** —
  a false positive here swings the whole score. Build a labeled test set of historical hedge-vs-cut
  statements and validate the grader against it (Phase 4 gate).
- **`supply_tell_signal` (0→1)** — supply catching demand: memory makers shifting HBM→commodity DRAM,
  capacity adds, book-to-bill < 1, inventory builds, first-time LTA deferral language.

## Historical-comparison hook

The digestor also produces the `news_sentiment` axis for the sentiment-analog vector. The compare view
puts today's headline sentiment next to the same axis from the pre-crash windows (Cisco 2000, GFC,
2021) — "today's capex/supply narrative most resembles the dot-com tape ~3 months pre-peak, with these
caveats." That comparison is rendered in the UI, sourced and dated.

## Simulation vs live-pull

To avoid hammering sources every cycle, the off-peak runs **simulate** from the cached/settled feed
(Asia close, overnight wires) rather than re-crawling everything live; a full live pull happens once
per scheduled slot, cached for the rest. The report states which feed snapshot it used.
