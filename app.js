/** CASSANDRA public dashboard — fetches KV Worker GET /api/latest, falls back to local API. */

const BANDS = [
  { max: 25, label: "Benign" },
  { max: 45, label: "Awareness" },
  { max: 65, label: "Mania" },
  { max: 80, label: "Danger" },
  { max: 101, label: "Blow-off" },
];
const MANIA_THRESHOLD = 65;
const LOCKED_FACTORS = new Set(["S", "B", "C"]);
const SLOT_LABELS = { 0: "Overnight", 12: "Asia PM", 21: "Pre-open" };

const cfg = window.CASSANDRA_CONFIG || {};

function isLocalDev() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

function animateCount(el, target, duration = 1200) {
  const start = performance.now();
  const from = 0;
  function frame(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (from + (target - from) * eased).toFixed(1);
    if (t < 1) requestAnimationFrame(frame);
    else el.textContent = Number(target).toFixed(1);
  }
  requestAnimationFrame(frame);
}

function setNeedle(crs) {
  const needle = document.getElementById("zone-needle");
  const pct = Math.max(0, Math.min(100, crs));
  requestAnimationFrame(() => {
    needle.style.left = `${pct}%`;
  });
}

function distanceToMania(crs) {
  const el = document.getElementById("distance-mania");
  if (crs >= MANIA_THRESHOLD) {
    el.textContent = `Inside ${bandFor(crs)} zone`;
    return;
  }
  const gap = (MANIA_THRESHOLD - crs).toFixed(1);
  el.textContent = `→ ${gap} pts below Mania`;
}

function bandFor(crs) {
  for (const b of BANDS) {
    if (crs < b.max) return b.label;
  }
  return "Blow-off";
}

function renderFactors(factors) {
  const keys = ["L", "V", "S", "B", "C"];
  document.getElementById("factors").innerHTML = keys.map((k) => {
    const locked = LOCKED_FACTORS.has(k);
    const val = factors?.[k];
    const display = locked ? "0.000" : (val != null ? Number(val).toFixed(3) : "—");
    return `
      <div class="factor-card${locked ? " locked" : ""}" title="${locked ? "Subscribe to unlock" : k}">
        ${locked ? '<span class="lock-icon" aria-hidden="true">🔒</span>' : ""}
        <div class="fk">${k}</div>
        <div class="fv">${display}</div>
      </div>`;
  }).join("");
}

function normalizeScore(raw) {
  if (!raw) return null;
  if (raw.score) return raw.score;
  return {
    crs: raw.crs,
    band: raw.band,
    fragility: raw.fragility,
    trigger: raw.trigger,
    phase: raw.phase,
    phase_confidence: raw.phase_confidence,
    coverage: raw.coverage,
    asof: raw.asof,
    band_halfwidth: raw.band_halfwidth,
    confidence: raw.confidence,
    factors: raw.factors,
    momentum_state: raw.momentum_state,
  };
}

async function fetchScore() {
  try {
    const r = await fetch("/api/latest");
    if (r.ok) return normalizeScore(await r.json());
  } catch (_) { /* Worker not wired */ }
  try {
    const r = await fetch("/api/dashboard");
    if (r.ok) return normalizeScore(await r.json());
  } catch (_) { /* offline */ }
  return null;
}

function populate(score) {
  if (!score) {
    document.getElementById("band-label").textContent = "No data yet";
    return;
  }
  animateCount(document.getElementById("crs"), score.crs);
  document.getElementById("band-label").textContent = score.band || bandFor(score.crs);
  distanceToMania(score.crs);
  setNeedle(score.crs);

  const cov = score.coverage != null ? (score.coverage * 100).toFixed(0) : "—";
  document.getElementById("coverage-note").textContent =
    `Coverage ${cov}% · wider band when data is thin`;

  document.getElementById("asof").textContent = score.asof ? `as of ${score.asof}` : "";
  document.getElementById("f").textContent = score.fragility?.toFixed(3) ?? "—";
  document.getElementById("t").textContent = score.trigger?.toFixed(3) ?? "—";
  document.getElementById("phase").textContent = (score.phase || "—").replace(/_/g, " ");

  const hw = score.band_halfwidth != null ? score.band_halfwidth : "—";
  const conf = score.confidence != null ? (score.confidence * 100).toFixed(0) : "—";
  document.getElementById("conf").textContent = `±${hw} · ${conf}%`;

  renderFactors(score.factors);
}

/* ── Countdown: 3× daily slots in Asia/Kuala_Lumpur (matches calendar_guard) ── */
function nextSlotMYT() {
  const slots = [0, 12, 21];
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kuala_Lumpur",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).formatToParts(now);
  const get = (t) => Number(parts.find((p) => p.type === t)?.value);
  const y = get("year"), mo = get("month"), d = get("day");
  let h = get("hour"), mi = get("minute"), s = get("second");

  for (const slotH of slots) {
    if (h < slotH || (h === slotH && mi === 0 && s === 0)) {
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

/* ── Geo payment routing ── */
async function detectCountry() {
  try {
    const r = await fetch("/api/geo");
    if (r.ok) {
      const { country } = await r.json();
      if (country) return country.toUpperCase();
    }
  } catch (_) { /* local fallback */ }
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  if (tz.includes("Kuala_Lumpur") || tz.includes("Singapore")) return "MY";
  const lang = navigator.language || "";
  if (lang.startsWith("zh")) return "CN";
  return "US";
}

function renderPaymentWidgets(country) {
  const p = cfg.payments || {};
  const subEl = document.getElementById("sub-buttons");
  const donEl = document.getElementById("donate-buttons");

  if (country === "CN") {
    const c = p.cn || {};
    subEl.innerHTML = `<a class="btn btn-primary" href="${c.airwallexSubscribe || "#"}" target="_blank" rel="noopener">Subscribe · Alipay / WeChat</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${c.airwallexDonate || "#"}" target="_blank" rel="noopener">Donate via Airwallex</a>`;
    return;
  }
  if (country === "MY") {
    const m = p.my || {};
    subEl.innerHTML = `<a class="btn btn-primary" href="${m.curlecSubscribe || "#"}" target="_blank" rel="noopener">Subscribe · Curlec (FPX / DuitNow)</a>`;
    donEl.innerHTML = `<a class="btn btn-secondary" href="${m.billplzDonate || "#"}" target="_blank" rel="noopener">Donate · Billplz</a>`;
    return;
  }
  const i = p.international || {};
  subEl.innerHTML = `<a class="btn btn-primary" href="${i.stripeSubscribe || "#"}" target="_blank" rel="noopener">Subscribe · $4.99/mo</a>`;
  donEl.innerHTML = `
    <a class="btn btn-secondary" href="${i.stripeDonate || "#"}" target="_blank" rel="noopener">Donate · Stripe</a>
    <a class="btn btn-secondary" href="${i.paypalDonate || "#"}" target="_blank" rel="noopener" style="margin-left:0.5rem">PayPal</a>`;
}

function setupNewsletter() {
  const form = document.getElementById("newsletter-form");
  if (cfg.newsletterAction) form.action = cfg.newsletterAction;
  form.addEventListener("submit", (e) => {
    if (!cfg.newsletterAction) {
      e.preventDefault();
      alert("Newsletter URL not configured — set CASSANDRA_CONFIG.newsletterAction in config.js");
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
    populate(await fetchScore());
    btn.disabled = false;
    btn.textContent = "Run cycle";
  };
}

async function init() {
  setupRunButton();
  setupNewsletter();
  tickCountdown();
  setInterval(tickCountdown, 1000);
  populate(await fetchScore());
  renderPaymentWidgets(await detectCountry());
}

init();
