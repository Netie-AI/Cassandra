/** CASSANDRA dashboard v2 — mockup-aligned, live data from /api/dashboard */

const BANDS = [
  { max: 25, label: "Benign" },
  { max: 45, label: "Awareness" },
  { max: 65, label: "Mania" },
  { max: 80, label: "Danger" },
  { max: 101, label: "Blow-off" },
];
const MANIA_THRESHOLD = 65;
const FACTOR_NAMES = { L: "Leverage", V: "Valuation", S: "Sentiment", B: "Breadth", C: "Catalyst" };
const PAID_TIERS = new Set(["report", "briefing", "agent"]);
const SLOT_LABELS = { 0: "Overnight", 12: "Asia PM", 21: "Pre-open" };

const cfg = window.CASSANDRA_CONFIG || {};
const CC = window.CassandraCommon;
let currentLang = "en";
let currentTier = "free";
let lastAsof = null;
let histChart = null;

function isLocalDev() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

function t(key) {
  return CC?.DASH_I18N?.[currentLang]?.[key] || CC?.DASH_I18N?.en?.[key] || key;
}

function lockedFactors() {
  return PAID_TIERS.has(currentTier) ? new Set() : new Set(["S", "B", "C"]);
}

function bandFor(crs) {
  for (const b of BANDS) if (crs < b.max) return b.label;
  return "Blow-off";
}

function riskColor(v) {
  if (v >= 0.7) return "#E24B4A";
  if (v >= 0.5) return "#D85A30";
  if (v >= 0.35) return "#BA7517";
  return "#639922";
}

function setBar(id, pct, color) {
  const el = document.getElementById(id);
  if (!el) return;
  requestAnimationFrame(() => {
    el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
    if (color) el.style.background = color;
  });
}

function animateCount(el, target, duration = 1300) {
  const start = performance.now();
  function frame(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = (target * eased).toFixed(1);
    if (p < 1) requestAnimationFrame(frame);
    else el.textContent = Number(target).toFixed(1);
  }
  requestAnimationFrame(frame);
}

function setNeedle(crs) {
  const needle = document.getElementById("zone-needle");
  if (!needle) return;
  setTimeout(() => { needle.style.left = `${Math.max(0, Math.min(100, crs))}%`; }, 150);
}

function distanceToMania(crs) {
  const el = document.getElementById("distance-mania");
  if (!el) return;
  if (crs >= MANIA_THRESHOLD) {
    el.textContent = `${t("insideZone")} ${bandFor(crs)} · spring loaded`;
    return;
  }
  const gap = (MANIA_THRESHOLD - crs).toFixed(1);
  el.textContent = `→ ${gap} ${t("belowMania")} · spring loaded, no spark confirmed yet`;
}

function renderFactors(factors) {
  const locked = lockedFactors();
  document.getElementById("factors").innerHTML = ["L", "V", "S", "B", "C"].map((k) => {
    const isLocked = locked.has(k);
    const val = factors?.[k];
    const pct = val != null ? Number(val) * 100 : 0;
    if (isLocked) {
      return `
        <div class="factor-card locked">
          <span class="lock-icon" aria-hidden="true">🔒</span>
          <div class="fk">${k}</div>
          <div class="fname">${FACTOR_NAMES[k]}</div>
          <div style="font-size:0.65rem;color:var(--muted);margin-top:0.5rem">subscribe</div>
        </div>`;
    }
    return `
      <div class="factor-card">
        <div class="fk">${k}</div>
        <div class="fname">${FACTOR_NAMES[k]}</div>
        <div class="fv">${val != null ? Number(val).toFixed(2) : "—"}</div>
        <div class="fbar"><div class="fbar-fill" style="width:${pct}%;background:${riskColor(Number(val))}"></div></div>
      </div>`;
  }).join("");
}

async function fetchDashboard() {
  try {
    const r = await fetch("/api/dashboard");
    if (r.ok) {
      const d = await r.json();
      return { score: d.score, tier: d.tier || "free" };
    }
  } catch (_) { /* offline */ }
  try {
    const r = await fetch("/api/latest");
    if (r.ok) return { score: await r.json(), tier: "free" };
  } catch (_) { /* offline */ }
  return { score: null, tier: "free" };
}

function populate(score) {
  if (!score) {
    document.getElementById("band-label").textContent = t("noData");
    return;
  }
  lastAsof = score.asof;
  animateCount(document.getElementById("crs"), score.crs);
  document.getElementById("band-label").textContent = (score.band || bandFor(score.crs)).toUpperCase();

  const hw = score.band_halfwidth != null ? score.band_halfwidth : 1;
  const lo = (score.crs - hw).toFixed(1);
  const hi = (score.crs + hw).toFixed(1);
  document.getElementById("band-range").textContent = `${lo} – ${hi}`;

  distanceToMania(score.crs);
  setNeedle(score.crs);

  const cov = score.coverage != null ? score.coverage : 0;
  document.getElementById("cov-pct").textContent = `${(cov * 100).toFixed(0)}%`;
  document.getElementById("coverage-note").textContent = t("coverageNote");
  setBar("bar-cov", cov * 100);

  document.getElementById("f").textContent = score.fragility?.toFixed(2) ?? "—";
  document.getElementById("t").textContent = score.trigger?.toFixed(2) ?? "—";
  setBar("bar-f", (score.fragility || 0) * 100, riskColor(score.fragility || 0));
  setBar("bar-t", (score.trigger || 0) * 100, riskColor(score.trigger || 0));

  const phaseLabel = (score.phase || "—").replace(/_/g, " ");
  document.getElementById("phase").textContent = phaseLabel;
  document.getElementById("phase-sub").textContent =
    score.phase_confidence != null ? `${(score.phase_confidence * 100).toFixed(0)}% confidence` : "";
  setBar("bar-phase", (score.phase_confidence || 0) * 100, "#BA7517");

  document.getElementById("f-sub").textContent =
    score.df_dt != null ? `dF/dt ${score.df_dt >= 0 ? "+" : ""}${Number(score.df_dt).toFixed(2)}` : "";
  document.getElementById("t-sub").textContent = "capex NLP watch";

  document.getElementById("asof")?.remove();
  renderFactors(score.factors);
}

async function loadHistoryChart() {
  if (typeof Chart === "undefined") return;
  let rows = [];
  try {
    const r = await fetch("/api/scores/history?limit=30");
    if (r.ok) rows = (await r.json()).history || [];
  } catch (_) { /* seed fallback */ }

  if (rows.length < 2) {
    rows = Array.from({ length: 30 }, (_, i) => ({ crs: 28 + i * 0.35 + Math.sin(i / 4) * 2 }));
  } else {
    rows = rows.reverse();
  }

  const labels = rows.map((row, i) => {
    if (row.asof) return row.asof.slice(5);
    const d = new Date();
    d.setDate(d.getDate() - (rows.length - 1 - i));
    return d.toLocaleDateString("en", { month: "short", day: "numeric" });
  });
  const data = rows.map((r) => r.crs);
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  const lc = dark ? "#5DCAA5" : "#1D9E75";
  const tc = dark ? "rgba(255,255,255,0.35)" : "rgba(0,0,0,0.35)";
  const gc = dark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)";

  const ctx = document.getElementById("histChart");
  if (!ctx) return;
  if (histChart) histChart.destroy();
  histChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data,
        borderColor: lc,
        borderWidth: 1.5,
        pointRadius: 2,
        tension: 0.35,
        fill: true,
        backgroundColor: dark ? "rgba(93,202,165,0.08)" : "rgba(29,158,117,0.07)",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: tc, font: { family: "IBM Plex Mono", size: 9 }, maxTicksLimit: 7 }, grid: { display: false } },
        y: { min: 15, max: 70, ticks: { color: tc, font: { family: "IBM Plex Mono", size: 9 } }, grid: { color: gc } },
      },
    },
  });
}

function nextSlotMYT() {
  const slots = [0, 12, 21];
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kuala_Lumpur",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).formatToParts(new Date());
  const get = (ty) => Number(parts.find((p) => p.type === ty)?.value);
  const y = get("year"), mo = get("month"), d = get("day"), h = get("hour");
  for (const slotH of slots) {
    if (h < slotH) return { slotH, target: zonedTime(y, mo, d, slotH, 0, 0) };
  }
  const tomorrow = new Date(Date.UTC(y, mo - 1, d + 1));
  return { slotH: 0, target: zonedTime(tomorrow.getUTCFullYear(), tomorrow.getUTCMonth() + 1, tomorrow.getUTCDate(), 0, 0, 0) };
}

function zonedTime(y, mo, d, h, mi, s) {
  return new Date(`${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}T${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}:${String(s).padStart(2, "0")}+08:00`);
}

function tickCountdown() {
  const { slotH, target } = nextSlotMYT();
  const diff = Math.max(0, target - Date.now());
  const hrs = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  document.getElementById("countdown").textContent =
    `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  document.getElementById("countdown-slot").textContent = SLOT_LABELS[slotH] || "";
}

async function detectCountry() {
  try {
    const r = await fetch("/api/geo");
    if (r.ok) return (await r.json()).country?.toUpperCase() || "US";
  } catch (_) { /* fallback */ }
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  if (/Kuala_Lumpur|Singapore/.test(tz)) return "MY";
  if ((navigator.language || "").startsWith("zh")) return "CN";
  return "US";
}

function renderPaymentWidgets(country) {
  const p = cfg.payments || {};
  const subEl = document.getElementById("sub-buttons");
  const donEl = document.getElementById("donate-buttons");
  if (country === "CN") {
    subEl.innerHTML = `<a class="btn btn-primary" href="${p.cn?.airwallexSubscribe || "/pricing"}">Alipay / WeChat</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${p.cn?.airwallexDonate || "#"}">Donate</a>`;
    return;
  }
  if (country === "MY") {
    subEl.innerHTML = `<a class="btn btn-primary" href="${p.my?.curlecSubscribe || "/pricing"}">FPX / DuitNow</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${p.my?.billplzDonate || "#"}">Billplz</a>`;
    return;
  }
  const i = p.international || {};
  subEl.innerHTML = `<a class="btn btn-primary" href="${i.stripeSubscribe || "/pricing?tier=report"}">Stripe · $4.99</a>`;
  donEl.innerHTML = `
    <a class="btn btn-secondary" href="${i.stripeDonate || "#"}">Stripe</a>
    <a class="btn btn-secondary" href="${i.paypalDonate || "#"}">PayPal</a>`;
}

function setupControls() {
  CC.initTheme(true);
  currentLang = CC.detectLang();
  CC.setLang(currentLang);
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.onclick = () => {
      currentLang = CC.setLang(btn.dataset.lang);
      if (window.__lastDashboard?.score) populate(window.__lastDashboard.score);
    };
  });
  document.getElementById("theme-toggle").onclick = () => {
    CC.toggleTheme();
    loadHistoryChart();
  };
  document.getElementById("btn-share").onclick = () => CC.shareReport(lastAsof);
  document.getElementById("btn-download-report").onclick = async () => {
    try {
      const r = await fetch("/newspaper-report");
      const html = await r.text();
      const asof = lastAsof || new Date().toISOString().slice(0, 10);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `cassandra-report-${asof}.html`;
      a.click();
      URL.revokeObjectURL(a.href);
      CC.toast("Report downloaded");
    } catch (_) {
      window.open(CC.reportUrl(lastAsof), "_blank");
    }
  };
  document.getElementById("btn-referral").onclick = async () => {
    await CC.copyText(CC.referralUrl());
    CC.toast("Referral link copied");
  };
}

function setupNewsletter() {
  document.getElementById("newsletter-form").addEventListener("submit", (e) => {
    if (!cfg.newsletterAction) {
      e.preventDefault();
      const email = e.target.email.value;
      window.location.href = `/subscribe?email=${encodeURIComponent(email)}`;
    }
  });
}

function setupRunButton() {
  const btn = document.getElementById("runBtn");
  if (!isLocalDev()) return;
  btn.classList.add("visible");
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Running…";
    await fetch("/api/run", { method: "POST" });
    const dash = await fetchDashboard();
    window.__lastDashboard = dash;
    currentTier = dash.tier;
    populate(dash.score);
    await loadHistoryChart();
    btn.disabled = false;
    btn.textContent = "Run cycle";
  };
}

async function init() {
  setupControls();
  setupRunButton();
  setupNewsletter();
  tickCountdown();
  setInterval(tickCountdown, 1000);
  const dash = await fetchDashboard();
  window.__lastDashboard = dash;
  currentTier = dash.tier;
  populate(dash.score);
  renderPaymentWidgets(await detectCountry());
  if (document.readyState === "complete") await loadHistoryChart();
  else window.addEventListener("load", () => loadHistoryChart());
}

init();
