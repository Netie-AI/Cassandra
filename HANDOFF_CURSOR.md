# HANDOFF → Next Cursor session

**Read first:** `status.md` · `files4/POLISH_FIXES.md` · `files4/GOLDEN_TRANSLATION_REFERENCE.md` · `files4/DEBUG_REASONING_LOG.md`

---

## Current state (2026-06-25, UI deploy prep)

### Fixed this round

| Issue | Root cause | Fix |
|-------|------------|-----|
| Homepage unstyled HTML | Missing `styles.css` + broken `</head>` in `index.html` | Restored full head block |
| Dead controls / `--` panels | Orphaned JS after `setupSignIn()` removal | Removed dangling block; guarded panel loads |
| Mixed EN/ZH on newspaper body | Body stored English only; labels in dict | `newspaper-bodies.js` golden ZH/MS wired in `setLang()` |
| Analog section stays English | No `setAnalogLang()` | `analog-resolution.js` i18n + homepage ids |
| Methodology 404 / unstyled | Route pointed to missing HTML | `docs-methodology.html` with shared docs chrome |
| Dates stay English on lang toggle | `toLocaleDateString` not re-run | `setDateLine()` / `updateReportDate()` on lang change |

### Canonical UI paths

- **Home:** `web/static/index.html` + `app.js` + `common.js`
- **Newspaper:** `web/static/newspaper-report.html` + `newspaper-bodies.js` + `newspaper.js`
- **Docs:** `docs-api.html`, `docs-institutional.html`, `docs-methodology.html` + `docs-chrome.js`
- **Golden translations:** `files4/GOLDEN_TRANSLATION_REFERENCE.md` (pipeline must match)
- **Debug discipline:** `files4/DEBUG_REASONING_LOG.md` (Cases 1–4)

### Verify before deploy

```bash
uvicorn api.main:app --port 8080
python -m pytest tests/ -q
```

Hard refresh `http://localhost:8080/` — expect styled grid, zero console errors, lang cycle EN→文→MS swaps dates + narrative + analog section.

---

## Short-term goals (next session)

1. **Pricing page i18n** — wire or keep lang button hidden (currently hidden per POLISH_FIXES)
2. **Live `/api/movers`** — Finnhub/Polygon feed; demo already leads MU/WDC in `demo-data.js`
3. **Pipeline translation storage** — store `(asof, lang)` bodies from `src/report.py`; frontend swaps API body when present, falls back to `newspaper-bodies.js`
4. **Platform card playgrounds** — link to docs/stock desk; do NOT ship ungated agent chat (see PARKING_LOT)
5. **Payment URLs** — set Stripe placeholders in `web/static/config.js`

---

## Long-term goals

| Goal | Phase |
|------|-------|
| Orchestrator `# WIRE:` end-to-end `--run` | Phase 5 |
| Supabase auth + tier webhooks | PARKING_LOT |
| Live analog archive (not illustrative demo) | Phase 5+ |
| Gated RAG agent chat on stock desk | Phase 5+ |
| Deploy crash.netie.ai (CF Worker + Pages) | Phase 9 |

---

## Phase 5 orchestrator (parallel track)

Claude APPROVED Phase 4. Wire `# WIRE:` in `src/orchestrator.py` on branch **`phase5-orchestrator`**.

See prior orchestrator checklist in git history / `HANDOFF_CLAUDE.md`.

**Ponytail rule:** smallest diff. LLM never computes CRS. No execution features.

═══ END HANDOFF CURSOR ═══
