# HOMEPAGE NOT RENDERING — debug spec for Cursor

## Symptom
Homepage shows `--` for all values (Score Inputs, Fear & Greed, Top Volatility all
empty). Language buttons, profile icon, and all controls are unresponsive. This is a
JS execution failure, NOT a data failure — the demo fallback never runs because the
script throws before reaching it.

## Step 1: open browser devtools console on http://localhost:8080/
Look for the FIRST red error. It is almost certainly one of:
- `Uncaught ReferenceError: X is not defined` (a function called before defined, or a
  missing import)
- `Uncaught TypeError: Cannot read properties of null` (getElementById returns null —
  an ID in JS doesn't match the HTML, often because the HTML was edited but JS wasn't)
- `Uncaught SyntaxError` (a broken template literal or stray bracket from a prior edit)
- A failed `fetch` that isn't wrapped in try/catch, killing the init function

## Step 2: the most likely culprit
The init code probably does `await fetch('/api/...')` at top level or in a function
that runs on load, WITHOUT try/catch. When the fetch rejects (or returns non-JSON
because an old server is cached), the whole init throws and NOTHING after it runs —
including button wiring and demo fallback.

Fix pattern — every data load must be independently guarded:
```js
async function loadDashboard() {
  // each section in its own try so one failure doesn't kill the rest
  try { renderWatchlist(await safeGet('/api/watchlist', DEMO.watchlist)); }
  catch (e) { console.warn('watchlist', e); renderWatchlist(DEMO.watchlist); }

  try { renderMovers(await safeGet('/api/movers?tf=1D', DEMO.movers)); }
  catch (e) { console.warn('movers', e); renderMovers(DEMO.movers); }

  try { renderFearGreed(await safeGet('/api/signals/fear_greed', DEMO.fg)); }
  catch (e) { console.warn('fg', e); renderFearGreed(DEMO.fg); }

  try { renderScoreInputs(await safeGet('/api/latest', DEMO.latest)); }
  catch (e) { console.warn('latest', e); renderScoreInputs(DEMO.latest); }
}

async function safeGet(url, fallback) {
  try {
    const r = await fetch(url);
    if (!r.ok) return fallback;
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('application/json')) return fallback;  // old server / HTML error page
    return await r.json();
  } catch { return fallback; }
}
```

## Step 3: button wiring must NOT depend on data load
Attach all event listeners synchronously on DOMContentLoaded, BEFORE any await:
```js
document.addEventListener('DOMContentLoaded', () => {
  wireLanguageToggle();   // synchronous — must run regardless of fetch
  wireThemeToggle();
  wireAccountMenu();
  wireTimeframeButton();
  loadDashboard();        // async — fire and forget, failures self-contained
});
```
If button wiring is currently INSIDE loadDashboard() or after an await, that's why
nothing is clickable. Move it out.

## Step 4: verify ID parity
Diff the getElementById('...') calls in app.js against the id="..." in index.html.
Any mismatch returns null and throws on the next property access. The home redesign
likely changed IDs in HTML without updating JS.

## Step 5: hard refresh
Ctrl+Shift+R. The browser may be running cached JS from the old layout. Also confirm
the server on 8080 is the NEW one (the handoff noted an old process was holding the
port — verify /api/movers returns JSON, not 404).

## Acceptance
- Console shows zero uncaught errors on load
- All four panels show demo data (not `--`)
- Language toggle, theme, profile menu, timeframe button all respond
