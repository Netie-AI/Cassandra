function renderStock(ticker) {
  const d = window.STOCK_DEMO?.[ticker];
  const el = document.getElementById("stock-app");
  if (!d || !el) return;
  const bandColor = d.band_color || "#92400E";
  const prem = d.premium || {};
  const editions = d.editions || [{ date: "2026-06-24", available: false }, { date: "2026-06-20", available: true }];
  const selectedDate = (editions.find((x) => x.available) || editions[0]).date;

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
          <div id="sd-date-list">${editions.map((ed) =>
            `<button type="button" class="sd-date-btn${ed.date === selectedDate ? " on" : ""}${ed.available ? "" : " locked"}" data-date="${ed.date}" data-available="${ed.available ? "1" : "0"}">${ed.date}</button>`
          ).join("")}</div>
          <div class="sh c-mt">Symbols</div>
          <div class="sd-symbol-buttons">
            <button type="button" class="sd-date-btn${ticker === "MU" ? " on" : ""}" data-symbol="MU">MU</button>
            <button type="button" class="sd-date-btn${ticker === "NOW" ? " on" : ""}" data-symbol="NOW">NOW</button>
          </div>
        </div>
      </aside>
      <div class="sd-main">
        <div class="sd-stale" id="sd-stale" hidden>Fetching verified quote…</div>
        <div class="sd-ticker-row">
          <div class="cm sd-symbol">${d.ticker}</div>
          <div class="sd-ticker-meta">
            <div class="sd-name">${d.name}</div>
            <div class="cm sd-quote" id="sd-quote">$${d.px} · ${d.sector || ""}</div>
            <div class="cm sd-quote" id="sd-asof"></div>
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
              <div class="sd-list">${d.fragility_drivers.map((x, i) => `<div class="sd-list-row${i < d.fragility_drivers.length - 1 ? " rb" : ""}">${x}</div>`).join("")}</div>
            </div>
            <div>
              <div class="sh">Trigger Watch</div>
              <div class="sd-list">${d.trigger_watch.map((x, i) => `<div class="sd-list-row${i < d.trigger_watch.length - 1 ? " rb" : ""}">${x}</div>`).join("")}</div>
            </div>
          </div>
          <div class="analyst-targets-panel" id="analyst-targets-panel">
            <div class="panel-head">Price Targets · Analyst Landscape</div>
            <div class="target-updated" id="target-updated"></div>
            <div class="target-row">
              <span class="target-source">JPMorgan</span>
              <span class="target-price" id="jpm-target">-</span>
              <span class="target-stance jpm-stance" id="jpm-stance">-</span>
              <span class="target-date" id="jpm-date">-</span>
            </div>
            <div class="target-row">
              <span class="target-source">Morningstar FV</span>
              <span class="target-price" id="ms-target">-</span>
              <span class="target-stance neutral-stance" id="ms-stance">-</span>
              <span class="target-date" id="ms-date">-</span>
            </div>
            <div class="target-row cassandra-row">
              <span class="target-source">Cassandra</span>
              <span class="target-price" id="cas-target">-</span>
              <span class="target-stance" id="cas-stance">Computing...</span>
              <span class="target-date">Live</span>
            </div>
            <div class="target-methodology">
              Cassandra target = Morningstar FV × phase_multiplier(CRS) × capex_signal_weight
              <span class="target-disclaimer">Research only. Not financial advice.</span>
            </div>
          </div>
          <div class="sd-analog-block">
            <div class="sh">Nearest Analog</div>
            <div class="cp sd-analog-text">${d.analog}</div>
          </div>
          <div class="sd-upsell">
            <p>Premium unlocks the timestamped change-log, level-by-level watchlist with invalidation markers, and the full 2000-vs-today news similarity engine with sourced comparables.</p>
            <a href="/subscribe?tier=agent&trial=1" class="sd-trial-link">Start 7-day free trial</a>
          </div>
          <div class="stock-chat-panel">
            <div class="stock-chat-header">
              Ask about <strong>${d.ticker}</strong>
              <span class="agent-counter">Agent generations: <strong id="agent-count">0</strong> / <span id="agent-limit">1</span> today</span>
            </div>
            <div id="stock-chat-messages" class="stock-chat-log"></div>
            <div class="stock-chat-input-row">
              <input id="stock-chat-input" type="text" placeholder="What changed for ${d.ticker} in this run?" />
              <button type="button" onclick="stockChatSend('${d.ticker}', '${selectedDate}')">→</button>
            </div>
            <div class="stock-chat-notice">Free: 3 questions/day · VIP: unlimited + agent generation</div>
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
            <p class="sd-sim-note">Similarity is descriptive, not predictive. Timing separation can exceed ±30 days.</p>
          </div>
        </div>
      </div>
    </div>
    <div id="sd-gate-overlay" class="auth-overlay" hidden>
      <div class="glass-card">
        <button type="button" class="glass-close" onclick="closeStockGate()">✕</button>
        <div class="glass-title">Subscriber edition</div>
        <div class="glass-msg">This edition is available to Report subscribers.</div>
        <button type="button" class="glass-submit" onclick="window.location.href='/pricing?tier=report'">Start free trial</button>
      </div>
    </div>
  `;

  renderPremium(prem);
  bindStockUI(el, ticker, selectedDate);
  loadUsage();
  loadAnalystTargets(d);
  fetchLiveQuote(ticker, d);
}

function renderPremium(prem) {
  try {
    const fq = prem.frag_quant || [];
    document.getElementById("frag-q").innerHTML = fq.map((r) => `<div class="sd-q-row rb"><span class="sd-q-name">${r.n}</span><span class="cm sd-q-val">${r.v}</span><span class="sd-q-d">${r.d}</span></div>`).join("");
    const lv = prem.levels || [];
    document.getElementById("lvl-q").innerHTML = lv.map((r) => `<div class="sd-q-row rb"><span class="sd-q-name">${r.n}</span><span class="cm sd-q-val">${r.v}</span><span class="sd-q-d">${r.m}</span></div>`).join("");
    const cl = prem.changelog || [];
    document.getElementById("clog").innerHTML = cl.map((r) => `<div class="sd-cl-row rb"><span class="sd-cl-dot" style="background:${r.c}"></span><span class="cm sd-cl-t">${r.t}</span><span class="sd-cl-d">${r.d}</span></div>`).join("");
    const sim = prem.similarity?.matches || [];
    document.getElementById("sim-rows").innerHTML = sim.map((r) => `<div class="sd-sim-row rb"><span class="cm sd-sim-val">${r.sim}</span><span class="sd-sim-src">${r.src}</span><span class="cm sd-sim-date">${r.date}</span></div>`).join("");
  } catch (_) { /* render guard */ }
}

function bindStockUI(el, ticker, selectedDate) {
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
  el.querySelectorAll(".sd-date-btn[data-date]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.available !== "1" && btn.dataset.date !== selectedDate) {
        openStockGate();
        return;
      }
      el.querySelectorAll(".sd-date-btn[data-date]").forEach((b) => b.classList.toggle("on", b === btn));
    });
  });
  el.querySelectorAll(".sd-date-btn[data-symbol]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.location.href = `/stocks/${btn.dataset.symbol}`;
    });
  });
}

function formatPriceRow(row, sector) {
  const up = Number(row.pct_change ?? row.pct ?? 0) >= 0;
  const color = up ? "#15803D" : "#B91C1C";
  const pctVal = Number(row.pct_change ?? row.pct ?? 0);
  const pctStr = `${up ? "+" : ""}${pctVal.toFixed(2)}%`;
  const status = String(row.market_status || "historical").toLowerCase();
  const label = String(row.market_status_label || status).toUpperCase();
  return `$${row.price || row.px} <span style="color:${color}">${pctStr}</span> · ${sector || ""} <span class="price-label" data-status="${status}">${label}</span>`;
}

async function fetchLiveQuote(ticker, demo) {
  const stale = document.getElementById("sd-stale");
  if (stale) stale.hidden = false;
  try {
    const r = await fetch(`/api/quote/${ticker}`);
    if (!r.ok) throw new Error("quote");
    const row = await r.json();
    const q = document.getElementById("sd-quote");
    if (q) q.innerHTML = formatPriceRow(row, demo.sector || "");
    const as = document.getElementById("sd-asof");
    if (as) as.textContent = `${row.source || "unknown"} · ${row.as_of || ""}`;
    return;
  } catch (_) {
    try {
      const r = await fetch(`/api/watchlist?user=stock-${ticker}`);
      if (!r.ok) return;
      const data = await r.json();
      const row = (data.rows || []).find((x) => x.sym === ticker.toUpperCase());
      if (!row?.px || row.px === "-") return;
      const q = document.getElementById("sd-quote");
      if (q) q.innerHTML = formatPriceRow(row, demo.sector || "");
      const as = document.getElementById("sd-asof");
      if (as) as.textContent = `${row.source || "unknown"} · ${row.asof || ""}`;
    } catch (_) { /* keep demo */ }
  } finally {
    if (stale) stale.hidden = true;
  }
}

async function loadAnalystTargets(d) {
  const t = d.targets || {};
  const fmt = (n) => (n == null ? "-" : `$${Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`);
  const set = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };
  set("target-updated", t.updated ? `last updated: ${t.updated}` : "");
  set("jpm-target", fmt(t.jpmorgan?.price));
  set("jpm-stance", t.jpmorgan?.stance || "-");
  set("jpm-date", t.jpmorgan?.date || "-");
  set("ms-target", fmt(t.morningstar?.fv));
  set("ms-stance", t.morningstar?.stance || "Fair Value");
  set("ms-date", t.morningstar?.date || "-");
  const fv = t.morningstar?.fv;
  if (!fv) {
    set("cas-target", "-");
    set("cas-stance", "No FV");
    return;
  }
  try {
    const q = new URLSearchParams({
      crs: String(d.crs_stock ?? 50),
      morningstar_fv: String(fv),
    });
    if (t.capex_score != null) q.set("capex_score", String(t.capex_score));
    const r = await fetch(`/api/stock/cassandra-target?${q}`);
    if (!r.ok) throw new Error("target");
    const row = await r.json();
    set("cas-target", fmt(row.target));
    set("cas-stance", row.stance || "-");
  } catch (_) {
    set("cas-target", "-");
    set("cas-stance", "Unavailable");
  }
}

async function loadUsage() {
  try {
    const CC = window.CassandraCommon;
    const h = CC?.authHeaders ? CC.authHeaders() : {};
    const r = await fetch("/api/agent/usage?date=today", { headers: h });
    if (!r.ok) return;
    const d = await r.json();
    const count = document.getElementById("agent-count");
    const limit = document.getElementById("agent-limit");
    if (count) count.textContent = String(d.generated ?? 0);
    if (limit) limit.textContent = d.limit == null ? "∞" : String(d.limit);
  } catch (_) { /* ignore */ }
}

async function stockChatSend(symbol, runId) {
  const input = document.getElementById("stock-chat-input");
  const msg = (input?.value || "").trim();
  if (!msg) return;
  const log = document.getElementById("stock-chat-messages");
  const append = (who, text) => {
    if (!log) return;
    log.innerHTML += `<div class="stock-chat-msg ${who}">${text}</div>`;
    log.scrollTop = log.scrollHeight;
  };
  append("user", msg);
  if (input) input.value = "";
  try {
    const CC = window.CassandraCommon;
    const r = await fetch("/api/agent/chat", {
      method: "POST",
      headers: CC?.authHeaders ? CC.authHeaders({ "Content-Type": "application/json" }) : { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, context: { symbol, run_id: runId } }),
    });
    const d = await r.json();
    if (d.reason === "tier_gated") {
      if (typeof window.openAuthOverlay === "function") window.openAuthOverlay("login");
      append("system", "Sign in required for this request.");
      return;
    }
    if (d.allowed === false) {
      append("system", d.reply || "Daily limit reached. Upgrade to VIP for unlimited access.");
      return;
    }
    append("assistant", d.reply || d.response || "No response.");
  } catch (_) {
    append("system", "Could not reach the agent.");
  }
}

function openStockGate() {
  document.getElementById("sd-gate-overlay")?.removeAttribute("hidden");
}

function closeStockGate() {
  document.getElementById("sd-gate-overlay")?.setAttribute("hidden", "hidden");
}

window.stockChatSend = stockChatSend;
window.openStockGate = openStockGate;
window.closeStockGate = closeStockGate;
