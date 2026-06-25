function renderStock(ticker) {
  const d = window.STOCK_DEMO?.[ticker];
  const el = document.getElementById("stock-app");
  if (!d || !el) return;

  const up = (d.pct ?? 0) >= 0;
  const pctColor = up ? "#15803D" : "#B91C1C";
  const pctStr = `${up ? "+" : ""}${Number(d.pct).toFixed(2)}%`;
  const bandColor = d.band_color || "#92400E";
  const prem = d.premium || {};
  const editions = d.editions || ["2026-06-24"];
  const selectedDate = editions[0];

  el.innerHTML = `
    <header class="sd-header">
      <div>
        <span class="cp sd-brand">Cassandra</span>
        <span class="sd-kicker">Stock Desk · demo</span>
      </div>
      <span class="cm sd-dateline">${new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase()} · ${new Date().toISOString().slice(11, 16)} UTC</span>
    </header>

    <div class="sd-layout">
      <aside class="sd-sidebar" id="sd-sidebar">
        <button type="button" class="sd-sidebar-toggle" id="sd-sidebar-toggle" aria-label="Toggle date sidebar">
          <i class="ti ti-layout-sidebar" aria-hidden="true"></i>
        </button>
        <div class="sd-sidebar-body">
          <div class="sh">Editions</div>
          <div id="sd-date-list">${editions.map((dt) =>
            `<button type="button" class="sd-date-btn${dt === selectedDate ? " on" : ""}" data-date="${dt}">${dt}</button>`
          ).join("")}</div>
        </div>
      </aside>

      <div class="sd-main">
        <div class="sd-stale" id="sd-stale" hidden>Possibly outdated. Fetching latest quote…</div>
        <div class="sd-ticker-row">
          <div class="cm sd-symbol">${d.ticker}</div>
          <div class="sd-ticker-meta">
            <div class="sd-name">${d.name}</div>
            <div class="cm sd-quote" id="sd-quote">$${d.px} <span style="color:${pctColor}">${pctStr}</span> · ${d.sector || ""}</div>
          </div>
          <div class="sd-crs-box">
            <div class="cm sd-crs-num" style="color:${bandColor}">${d.crs_stock}</div>
            <div class="sd-crs-band" style="color:${bandColor}">Stock CRS · ${d.band}</div>
          </div>
        </div>

        <div class="sd-tabs">
          <button type="button" class="sd-tab on" data-view="free">Free view</button>
          <button type="button" class="sd-tab" data-view="prem">Premium view</button>
        </div>

        <div id="sd-free" class="sd-view">
          <div class="sd-two-col">
            <div>
              <div class="sh">Fragility Drivers</div>
              <div class="sd-list">${d.fragility_drivers.map((x, i) =>
                `<div class="sd-list-row${i < d.fragility_drivers.length - 1 ? " rb" : ""}">${x}</div>`
              ).join("")}</div>
            </div>
            <div>
              <div class="sh">Trigger Watch</div>
              <div class="sd-list">${d.trigger_watch.map((x, i) =>
                `<div class="sd-list-row${i < d.trigger_watch.length - 1 ? " rb" : ""}">${x}</div>`
              ).join("")}</div>
            </div>
          </div>
          <div class="sd-analog-block">
            <div class="sh">Nearest Analog</div>
            <div class="cp sd-analog-text">${d.analog}</div>
          </div>
          <div class="sd-upsell">
            <p>Premium unlocks the timestamped change-log, level-by-level watchlist with invalidation markers, and the full 2000-vs-today news similarity engine with sourced comparables.</p>
            <a href="/subscribe?tier=agent&trial=1" class="sd-trial-link">Start 7-day free trial →</a>
          </div>
        </div>

        <div id="sd-prem" class="sd-view" hidden>
          <div class="sd-two-col sd-mb">
            <div>
              <div class="sh">Fragility · Quantified</div>
              <div id="frag-q"></div>
            </div>
            <div>
              <div class="sh">Watchlist Levels</div>
              <div id="lvl-q"></div>
            </div>
          </div>
          <div class="sd-mb">
            <div class="sh">Change Log · Since Last Edition</div>
            <div id="clog"></div>
          </div>
          <div class="sd-sim-box">
            <div class="sd-sim-head">
              <span class="cp sd-sim-title">News similarity to ${prem.similarity?.window || "March 2000"}</span>
              <span class="cm sd-sim-score" style="color:#B91C1C">${prem.similarity?.score ?? "n/a"}</span>
            </div>
            <div id="sim-rows"></div>
            <p class="sd-sim-note">Cosine similarity of today's news embeddings vs the 60-day window preceding the Mar 2000 NASDAQ peak. Each match links to the archived source. Similarity is descriptive, not predictive. Timing separation can exceed ±30 days.</p>
          </div>
        </div>

        <footer class="sd-footer">
          <a href="/">Home</a> · <a href="/newspaper-report">Newspaper</a> · <a href="/pricing">Plans</a>
          · <a href="/stocks/MU">MU</a> · <a href="/stocks/NOW">NOW</a>
        </footer>
      </div>
    </div>
  `;

  try {
    const fq = prem.frag_quant || [];
    document.getElementById("frag-q").innerHTML = fq.map((r) =>
      `<div class="sd-q-row rb"><span class="sd-q-name">${r.n}</span><span class="cm sd-q-val">${r.v}</span><span class="sd-q-d">${r.d}</span></div>`
    ).join("");

    const lv = prem.levels || [];
    document.getElementById("lvl-q").innerHTML = lv.map((r) =>
      `<div class="sd-q-row rb"><span class="sd-q-name">${r.n}</span><span class="cm sd-q-val">${r.v}</span><span class="sd-q-d">${r.m}</span></div>`
    ).join("");

    const cl = prem.changelog || [];
    document.getElementById("clog").innerHTML = cl.map((r) =>
      `<div class="sd-cl-row rb"><span class="sd-cl-dot" style="background:${r.c}"></span><span class="cm sd-cl-t">${r.t}</span><span class="sd-cl-d">${r.d}</span></div>`
    ).join("");

    const sim = prem.similarity?.matches || [];
    document.getElementById("sim-rows").innerHTML = sim.map((r) =>
      `<div class="sd-sim-row rb"><span class="cm sd-sim-val">${r.sim}</span><span class="sd-sim-src">${r.src}</span><span class="cm sd-sim-date">${r.date}</span></div>`
    ).join("");
  } catch (_) { /* demo render guard */ }

  el.querySelectorAll(".sd-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.view;
      el.querySelectorAll(".sd-tab").forEach((t) => t.classList.toggle("on", t.dataset.view === view));
      document.getElementById("sd-free").hidden = view !== "free";
      document.getElementById("sd-prem").hidden = view !== "prem";
    });
  });

  document.getElementById("sd-sidebar-toggle")?.addEventListener("click", () => {
    document.getElementById("sd-sidebar")?.classList.toggle("collapsed");
  });

  el.querySelectorAll(".sd-date-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      el.querySelectorAll(".sd-date-btn").forEach((b) => b.classList.toggle("on", b === btn));
      const stale = document.getElementById("sd-stale");
      if (stale) {
        stale.hidden = false;
        setTimeout(() => { stale.hidden = true; }, 1200);
      }
    });
  });

  fetchLiveQuote(ticker, d);
}

async function fetchLiveQuote(ticker, demo) {
  try {
    const r = await fetch(`/api/watchlist?user=stock-${ticker}`);
    if (!r.ok) return;
    const data = await r.json();
    const row = (data.rows || []).find((x) => x.sym === ticker.toUpperCase());
    if (!row?.px || row.px === "—") return;
    const up = Number(row.pct) >= 0;
    const color = up ? "#15803D" : "#B91C1C";
    const pctStr = `${up ? "+" : ""}${Number(row.pct).toFixed(2)}%`;
    const q = document.getElementById("sd-quote");
    if (q) q.innerHTML = `$${row.px} <span style="color:${color}">${pctStr}</span> · ${demo.sector || ""}`;
  } catch (_) { /* demo price stays */ }
}
