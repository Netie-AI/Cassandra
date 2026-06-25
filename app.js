/** CASSANDRA public dashboard */

const BANDS = [
  { max: 25, label: "Benign" },
  { max: 45, label: "Awareness" },
  { max: 65, label: "Mania" },
  { max: 80, label: "Danger" },
  { max: 101, label: "Blow-off" },
];
const MANIA_THRESHOLD = 65;
const PAID_TIERS = new Set(["report", "briefing", "agent"]);
const SLOT_LABELS = { 0: "Overnight", 12: "Asia PM", 21: "Pre-open" };

const cfg = window.CASSANDRA_CONFIG || {};
const CC = window.CassandraCommon;
let currentLang = "en";
let currentTier = "free";
let lastAsof = null;

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

function animateCount(el, target, duration = 1200) {
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
  const pct = Math.max(0, Math.min(100, crs));
  requestAnimationFrame(() => { needle.style.left = `${pct}%`; });
}

function bandFor(crs) {
  for (const b of BANDS) {
    if (crs < b.max) return b.label;
  }
  return "Blow-off";
}

function distanceToMania(crs) {
  const el = document.getElementById("distance-mania");
  if (crs >= MANIA_THRESHOLD) {
    el.textContent = `${t("insideZone")} ${bandFor(crs)} zone`;
    return;
  }
  el.textContent = `→ ${(MANIA_THRESHOLD - crs).toFixed(1)} ${t("belowMania")}`;
}

function renderFactors(factors) {
  const locked = lockedFactors();
  document.getElementById("factors").innerHTML = ["L", "V", "S", "B", "C"].map((k) => {
    const isLocked = locked.has(k);
    const val = factors?.[k];
    const display = isLocked ? "0.000" : (val != null ? Number(val).toFixed(3) : "—");
    return `
      <div class="factor-card${isLocked ? " locked" : ""}">
        ${isLocked ? '<span class="lock-icon" aria-hidden="true">🔒</span>' : ""}
        <div class="fk">${k}</div>
        <div class="fv">${display}</div>
      </div>`;
  }).join("");
}

function normalizePayload(raw) {
  if (!raw) return { score: null, tier: "free" };
  if (raw.score) return { score: raw.score, tier: raw.tier || "free" };
  return { score: raw, tier: "free" };
}

async function fetchDashboard() {
  try {
    const r = await fetch("/api/dashboard");
    if (r.ok) return normalizePayload(await r.json());
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
  document.getElementById("band-label").textContent = score.band || bandFor(score.crs);
  distanceToMania(score.crs);
  setNeedle(score.crs);

  const cov = score.coverage != null ? (score.coverage * 100).toFixed(0) : "—";
  document.getElementById("coverage-note").textContent =
    `${t("coverage")} ${cov}% · ${t("coverageNote")}`;
  document.getElementById("asof").textContent =
    score.asof ? `${t("asof")} ${score.asof}` : "";

  document.getElementById("f").textContent = score.fragility?.toFixed(3) ?? "—";
  document.getElementById("t").textContent = score.trigger?.toFixed(3) ?? "—";
  document.getElementById("phase").textContent = (score.phase || "—").replace(/_/g, " ");

  const hw = score.band_halfwidth ?? "—";
  const conf = score.confidence != null ? (score.confidence * 100).toFixed(0) : "—";
  document.getElementById("conf").textContent = `±${hw} · ${conf}%`;
  renderFactors(score.factors);
}

function nextSlotMYT() {
  const slots = [0, 12, 21];
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kuala_Lumpur",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).formatToParts(new Date());
  const get = (ty) => Number(parts.find((p) => p.type === ty)?.value);
  const y = get("year"), mo = get("month"), d = get("day");
  const h = get("hour");

  for (const slotH of slots) {
    if (h < slotH) {
      return { slotH, target: zonedTime(y, mo, d, slotH, 0, 0) };
    }
  }
  const tomorrow = new Date(Date.UTC(y, mo - 1, d + 1));
  return {
    slotH: 0,
    target: zonedTime(tomorrow.getUTCFullYear(), tomorrow.getUTCMonth() + 1, tomorrow.getUTCDate(), 0, 0, 0),
  };
}

function zonedTime(y, mo, d, h, mi, s) {
  const iso = `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}T${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}:${String(s).padStart(2, "0")}+08:00`;
  return new Date(iso);
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
    const c = p.cn || {};
    subEl.innerHTML = `<a class="btn btn-primary" href="${c.airwallexSubscribe || "/pricing?tier=report"}" target="_blank" rel="noopener">Subscribe · Alipay / WeChat</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${c.airwallexDonate || "#"}" target="_blank" rel="noopener">Donate</a>`;
    return;
  }
  if (country === "MY") {
    const m = p.my || {};
    subEl.innerHTML = `<a class="btn btn-primary" href="${m.curlecSubscribe || "/pricing?tier=report"}" target="_blank" rel="noopener">Subscribe · Curlec</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${m.billplzDonate || "#"}" target="_blank" rel="noopener">Donate · Billplz</a>`;
    return;
  }
  const i = p.international || {};
  subEl.innerHTML = `<a class="btn btn-primary" href="${i.stripeSubscribe || "/pricing?tier=report"}" target="_blank" rel="noopener">Subscribe · $4.99/mo</a>`;
  donEl.innerHTML = `
    <a class="btn btn-secondary" href="${i.stripeDonate || "#"}" target="_blank" rel="noopener">Stripe</a>
    <a class="btn btn-secondary" href="${i.paypalDonate || "#"}" target="_blank" rel="noopener">PayPal</a>`;
}

function setupControls() {
  CC.initTheme(true);
  currentLang = CC.detectLang();
  CC.setLang(currentLang);

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.onclick = () => {
      currentLang = CC.setLang(btn.dataset.lang);
      const { score } = window.__lastDashboard || {};
      if (score) populate(score);
    };
  });
  document.getElementById("theme-toggle").onclick = () => CC.toggleTheme();

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
  document.getElementById("referral-display").textContent = CC.referralCode();
}

function setupNewsletter() {
  const form = document.getElementById("newsletter-form");
  if (cfg.newsletterAction) form.action = cfg.newsletterAction;
  form.addEventListener("submit", (e) => {
    if (!cfg.newsletterAction) {
      e.preventDefault();
      window.location.href = `/subscribe?email=${encodeURIComponent(form.email.value)}`;
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
}

init();
