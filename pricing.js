const cfg = window.CASSANDRA_CONFIG || {};

const TIERS = [
  {
    id: "free",
    key: "free",
    name: "Free",
    price: "$0",
    period: "",
    trial: "Always",
    features: ["CRS + band (2-day delay)", "Headline + direction", "Sentiment read", "Historical echo (teaser)"],
    cta: null,
    href: "/",
    rec: false,
  },
  {
    id: "report",
    key: "rep",
    name: "Report",
    price: "$4.99",
    period: " /mo",
    trial: "7 days free · new subscribers",
    features: ["All in Free", "Full factor breakdown", "30-day signal history", "Analog map preview", "Trigger board"],
    cta: "Start free trial",
    rec: true,
  },
  {
    id: "briefing",
    key: "pro",
    name: "Pro Desk",
    price: "$9.99",
    period: " /mo",
    trial: "7 days free · new subscribers",
    features: ["All in Report", "Real-time trigger alerts", "Scenario grids", "Watchlist price levels", "Priority edition"],
    cta: "Start free trial",
    rec: false,
  },
  {
    id: "agent",
    key: "api",
    name: "API",
    price: "$49.99",
    period: " /mo",
    trial: "7 days free · new subscribers",
    features: ["All in Pro", "JSON API · 3× daily", "Webhook alerts", "Custom baskets", "Institutional data feed"],
    cta: "Start free trial",
    rec: false,
  },
];

const COMPARE_ROWS = [
  { label: "Live score (today)", report: true, briefing: true, agent: true },
  { label: "Newspaper edition", report: true, briefing: true, agent: true },
  { label: "API / JSON access", report: true, briefing: true, agent: true },
  { label: "Analog resolution (next-day/week/month)", report: true, briefing: true, agent: true },
  { label: "Deep analog brief", report: false, briefing: true, agent: true },
  { label: "Ranked news panel", report: false, briefing: true, agent: true },
  { label: "Stock agents + API keys", report: false, briefing: false, agent: true },
];

const I18N_PRICING = {
  en: {
    headline: "Start with a full edition. No commitments.",
    lead: "First-time subscribers receive the complete edition free for 7 days. Cancel anytime before renewal.",
    compare_title: "Compare plans",
    compare_lead: "Research support only. We score risk, we don't trade for you.",
    tiers: {
      free: { name: "Free", cta: null, trial: "Always" },
      report: { name: "Report", cta: "Start free trial", trial: "7 days free · new subscribers" },
      briefing: { name: "Pro Desk", cta: "Start free trial", trial: "7 days free · new subscribers" },
      agent: { name: "API", cta: "Start free trial", trial: "7 days free · new subscribers" },
    },
    compare_rows: [
      "Live score (today)", "Newspaper edition", "API / JSON access",
      "Analog resolution (next-day/week/month)", "Deep analog brief",
      "Ranked news panel", "Stock agents + API keys",
    ],
    home_cta: "Home →",
  },
  zh: {
    headline: "从完整版本开始。无需承诺。",
    lead: "首次订阅者可免费试用完整版本7天。续费前可随时取消。",
    compare_title: "比较方案",
    compare_lead: "仅限研究支持。我们评估风险，不代客操盘。",
    tiers: {
      free: { name: "免费版", cta: null, trial: "永久免费" },
      report: { name: "报告版", cta: "开始免费试用", trial: "7天免费试用 · 新订阅者" },
      briefing: { name: "专业桌面版", cta: "开始免费试用", trial: "7天免费试用 · 新订阅者" },
      agent: { name: "API接入", cta: "开始免费试用", trial: "7天免费试用 · 新订阅者" },
    },
    compare_rows: [
      "实时评分（今日）", "报纸版面", "API / JSON接入",
      "类比分辨率（次日/周/月）", "深度类比简报",
      "排名新闻面板", "股票代理 + API密钥",
    ],
    home_cta: "首页 →",
  },
  ms: {
    headline: "Mulakan dengan edisi penuh. Tanpa komitmen.",
    lead: "Pelanggan baharu menerima edisi lengkap percuma selama 7 hari. Boleh batalkan sebelum pembaharuan.",
    compare_title: "Bandingkan pelan",
    compare_lead: "Sokongan penyelidikan sahaja. Kami menilai risiko, bukan berniaga untuk anda.",
    tiers: {
      free: { name: "Percuma", cta: null, trial: "Sentiasa" },
      report: { name: "Edisi Laporan", cta: "Mulakan percubaan percuma", trial: "7 hari percuma · pelanggan baharu" },
      briefing: { name: "Meja Pro", cta: "Mulakan percubaan percuma", trial: "7 hari percuma · pelanggan baharu" },
      agent: { name: "Akses API", cta: "Mulakan percubaan percuma", trial: "7 hari percuma · pelanggan baharu" },
    },
    compare_rows: [
      "Skor langsung (hari ini)", "Edisi akhbar", "Akses API / JSON",
      "Resolusi analog (hari seterusnya/minggu/bulan)", "Ringkasan analog mendalam",
      "Panel berita berperingkat", "Agen saham + kunci API",
    ],
    home_cta: "Laman utama →",
  },
};

let currentLang = "en";
let currentRef = "";
let currentHighlight = null;

function payUrl(tierId) {
  const p = cfg.payments?.international || {};
  const map = {
    report: cfg.stripe_report_url || p.stripeReport || p.stripeSubscribe || "",
    briefing: cfg.stripe_pro_url || p.stripeBriefing || "",
    agent: cfg.stripe_api_url || p.stripeAgent || "",
  };
  return map[tierId] || "";
}

function payReady(tierId) {
  return Boolean(payUrl(tierId));
}

function ctaHtml(tier, ref, ctaText, extraClass) {
  const url = payUrl(tier.id);
  const cls = `pricing-cta${extraClass || ""}`;
  if (!url) {
    return `<span class="${cls} pricing-cta-disabled" title="Coming soon" aria-disabled="true">${ctaText}</span>`;
  }
  return `<a class="${cls}" href="${url}?ref=${ref}&trial=1">${ctaText}</a>`;
}

function featHtml(features) {
  return features.map((f) => `<div class="pricing-feat-row">· ${f}</div>`).join("");
}

function renderGrid(ref, highlight, t) {
  t = t || I18N_PRICING[currentLang] || I18N_PRICING.en;
  const grid = document.getElementById("tier-grid");
  if (!grid) return;
  grid.innerHTML = TIERS.map((tier) => {
    const loc = t.tiers[tier.id] || {};
    const name = loc.name || tier.name;
    const trial = loc.trial || tier.trial;
    const cta = loc.cta !== undefined ? loc.cta : tier.cta;
    const href = tier.href || (payReady(tier.id) ? `${payUrl(tier.id)}?ref=${ref}&trial=1` : "");
    const colClass = `pricing-col${tier.rec ? " pricing-col-rec" : ""}${highlight === tier.id ? " pricing-highlight" : ""}`;
    const ctaBlock = cta
      ? (tier.href
        ? `<a class="pricing-cta" href="${href}">${cta}</a>`
        : ctaHtml(tier, ref, cta))
      : `<a class="pricing-cta" href="${href || "/"}">${t.home_cta || "Home →"}</a>`;
    return `<div class="${colClass}">
      <div class="sh${tier.rec ? " pricing-rec-label" : ""}">${name}</div>
      <div class="cm pricing-price">${tier.price}${tier.period ? `<span class="pricing-period">${tier.period}</span>` : ""}</div>
      <div class="pricing-freq">${trial}</div>
      <div class="pricing-feats">${featHtml(tier.features)}</div>
      ${ctaBlock}
    </div>`;
  }).join("");
}

function renderCompare(ref, t) {
  t = t || I18N_PRICING[currentLang] || I18N_PRICING.en;
  const el = document.getElementById("compare-matrix");
  if (!el) return;
  const paid = TIERS.filter((tier) => tier.id !== "free");
  const head = `<div class="compare-row compare-head"><span>Feature</span>${paid.map((tier) => {
    const loc = t.tiers[tier.id] || {};
    const name = loc.name || tier.name;
    return `<span>${name}<br><small>${tier.price}${tier.period}</small></span>`;
  }).join("")}</div>`;
  const body = COMPARE_ROWS.map((row, idx) => {
    const label = t.compare_rows[idx] || row.label;
    const cells = [row.report, row.briefing, row.agent]
      .map((v) => `<span>${v ? "✓" : "-"}</span>`)
      .join("");
    return `<div class="compare-row"><span>${label}</span>${cells}</div>`;
  }).join("");
  const ctas = `<div class="compare-row compare-cta"><span></span>${paid.map((tier) => {
    const loc = t.tiers[tier.id] || {};
    const cta = loc.cta !== undefined ? loc.cta : tier.cta;
    return `<span>${ctaHtml(tier, ref, cta)}</span>`;
  }).join("")}</div>`;
  el.innerHTML = head + body + ctas;
}

function setLang(lang) {
  if (!I18N_PRICING[lang]) lang = "en";
  currentLang = lang;
  const t = I18N_PRICING[lang];
  const h = document.querySelector(".pricing-headline");
  if (h) h.textContent = t.headline;
  const lead = document.getElementById("trial-lead");
  if (lead && !lead.dataset.apiOverride) lead.textContent = t.lead;
  const ct = document.querySelector(".compare-title");
  if (ct) ct.textContent = t.compare_title;
  const cl = document.querySelector(".compare-lead");
  if (cl) cl.textContent = t.compare_lead;
  renderGrid(currentRef, currentHighlight, t);
  renderCompare(currentRef, t);
  document.documentElement.lang = lang === "zh" ? "zh-CN" : lang === "ms" ? "ms" : "en";
  try { localStorage.setItem("cassandra-lang", lang); } catch (_) { /* ignore */ }
}

async function loadTrialCopy() {
  try {
    const r = await fetch("/api/subscribe/options?tier=report&first_sub=true");
    if (!r.ok) return;
    const d = await r.json();
    const lead = document.getElementById("trial-lead");
    if (lead && d.trial_message) {
      lead.textContent = `First-time subscribers: ${d.trial_message}. Cancel anytime before renewal.`;
      lead.dataset.apiOverride = "1";
    }
  } catch (_) { /* static fallback */ }
}

async function init() {
  CassandraCommon.initThemeToggle(false);
  CassandraCommon.initAccountMenu();
  const params = new URLSearchParams(location.search);
  currentRef = params.get("ref") || CassandraCommon.referralCode();
  currentHighlight = params.get("tier");
  try {
    const saved = localStorage.getItem("cassandra-lang");
    if (saved && I18N_PRICING[saved]) currentLang = saved;
  } catch (_) { /* ignore */ }
  CassandraCommon.initLangCycle((lang) => setLang(lang));
  setLang(currentLang);
  const payNote = document.getElementById("pay-note");
  if (payNote && CassandraCommon.paymentMethodHtml) {
    payNote.innerHTML = CassandraCommon.paymentMethodHtml();
  }
  await loadTrialCopy();
  if (currentHighlight) {
    document.querySelector(".pricing-highlight")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

init();
