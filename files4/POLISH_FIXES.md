# POLISH FIXES — this round

## Language toggle still not translating dates / body
- ROOT: see DEBUG_REASONING_LOG case 2 + 4 + GOLDEN_TRANSLATION_REFERENCE.
- **Homepage:** fixed via `setDateLine()` + expanded `T` dict (2026-06-25).
- **Newspaper:** golden bodies wired in `newspaper-bodies.js` + `applyNewspaperBodies()` in `setLang()`.
- **Remaining:** pipeline must store `(asof, lang)` bodies from `src/report.py` so live editions replace hardcoded golden fallback.

## Language button square too small / overlaps icon
- The cycling lang button: increase min-width and horizontal padding so the icon +
  label never overlap. Use: height 28px, padding 0 9px, gap 6px between icon and label.
- On the PRICING page the lang toggle "changing language totally useless" — pricing
  page strings aren't wired to i18n at all. Either wire them, or (faster for tomorrow)
  make pricing English-only and HIDE the language button on that page until wired.
  Do not show a language button that does nothing.

## Account dropdown hard to see
- Add background + subtle transparency so it reads against page content:
  background: var(--color-background-primary);
  border: 0.5px solid var(--color-border-secondary);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  (The shadow is the fix — a floating menu needs separation from content. ~10-12% alpha.)

## Docs pages (institutional / API / methodology)
- "blurry line after 'not a sales document'": that subhead is redundant and reads
  awkwardly. REMOVE the "Explanatory reference, not a sales document" line entirely.
  The page should just explain. Don't announce what kind of document it is.
- Institutional + API pages: the lang button does nothing here AND theme/profile are
  mislaid. FIX HEADER on ALL docs pages: nav left; theme + profile icons on the FIRST
  line, right-aligned; match the home header exactly. Lang button hidden on docs (they're
  English reference) OR wired — not present-but-dead.
- EM-DASH SWEEP: institutional + API docs both contain "—". Run the lint. Replace all.
## Methodology page STILL has no styling
- **Fixed 2026-06-25:** `web/static/docs-methodology.html` with shared docs chrome.

## Top Volatility not surfacing Micron / SanDisk
- The movers list is hardcoded demo data (per your API doc, /api/movers is demo).
  It won't reflect real top movers until wired to a live feed.
- For the DEMO, at minimum include the names the user expects to see big: MU (Micron),
  SNDK/WDC (SanDisk/Western Digital), plus the existing set. Update demo-data.js.
- Real fix: wire /api/movers to a live mover feed (Finnhub / Polygon — both keys
  present per .env) sorted by absolute % move, sector-filtered to tech+semis, top 10.

## Edit watchlist — needs search/dropdown, not raw comma input
- Current: "comma-separated tickers" textbox is too unfriendly.
- Better: a small searchable picker. Start with a seeded list of common tickers
  (LEU, NVDA, MSFT, AMZN, TSM, MU, NOW, BABA, AMD, AVGO, SMCI, ARM, WDC, ...) shown as
  toggle chips; plus a search box that filters as you type and adds on click.
- Save to localStorage + POST /api/watchlist/update (already exists).

## Platform cards must lead to real playgrounds (not placeholder links)
- "Build Your AI Agent" currently links to /stocks/NOW. The agent playground IS the
  stock desk page with a chat panel. On login/paid, these cards open the REAL on-site
  chat, not a marketing link.
- BUT: the agent chat is NOT ready for tomorrow (gating + RAG incomplete). So for now:
  - Logged out / free: card links to the docs/whitepaper explaining the feature.
  - The actual chat playground ships AFTER the gate + RAG are real.
  Do not wire a live ungated chat to these cards for launch.
