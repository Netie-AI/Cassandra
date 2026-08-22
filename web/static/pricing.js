const cfg = window.CASSANDRA_CONFIG || {};

const TIERS = [
  {
    id: "free",
    key: "free",
    name: "Free",
    price: "$0",
    period: "",
    trial: "After day 90, unless you subscribe",
    features: ["Live CRS + band", "L + V factor scores", "3x daily updates", "Free email summary"],
    cta: null,
    href: "/",
    rec: false,
  },
  {
    id: "report",
    key: "rep",
    name: "The Report",
    price: "$4.99",
    period: " /mo",
    trial: "Optional after the 90-day Agent trial",
    features: ["Everything in Free", "Full 5-factor daily report", "capex NLP signal", "Historical analog comparison", "Email delivery daily"],
    cta: "Subscribe",
    rec: true,
  },
  {
    id: "briefing",
    key: "pro",
    name: "The Briefing",
    price: "$9.99",
    period: " /mo",
    trial: "Optional after the 90-day Agent trial",
    features: ["Everything in Report", "10-page deep analysis", "AI-generated insights", "Side-by-side 2000/2008 analog", "Source attribution on all data"],
    cta: "Subscribe",
    rec: false,
  },
  {
    id: "agent",
    key: "api",
    name: "The Agent",
    price: "$49.99",
    period: " /mo",
    trial: "Included free for 3 months, then Free",
    features: ["Everything in Briefing", "Custom stock watchlist", "Stock-specific crash scores", "API access (JSON endpoint)", "Chat with Cassandra (50/day)"],
    cta: "Subscribe after trial",
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
    headline: "3 months Agent, then Free",
    lead: "Every new account gets The Agent free for 3 months from registration. No charge. On day 90 you drop to Free. Subscribe after that if you want Report, Briefing, or Agent. The trial does not auto-convert to a paid plan.",
    compare_title: "Compare plans",
    compare_lead: "Research support only. We score risk, we don't trade for you.",
    tiers: {
      free: { name: "Free", cta: null, trial: "After day 90, unless you subscribe" },
      report: { name: "The Report", cta: "Subscribe", trial: "Optional after the 90-day Agent trial" },
      briefing: { name: "The Briefing", cta: "Subscribe", trial: "Optional after the 90-day Agent trial" },
      agent: { name: "The Agent", cta: "Subscribe after trial", trial: "Included free for 3 months, then Free" },
    },
    compare_rows: [
      "Live score (today)", "Newspaper edition", "API / JSON access",
      "Analog resolution (next-day/week/month)", "Deep analog brief",
      "Ranked news panel", "Stock agents + API keys",
    ],
    home_cta: "Home →",
  },
  zh: {
    headline: "先用三个月 Agent，然后回到免费版",
    lead: "新账号注册起 90 天内免费使用 The Agent。不扣费。第 90 天自动降为免费版。之后可自行订阅 Report / Briefing / Agent。试用不会自动转成付费。",
    compare_title: "比较方案",
    compare_lead: "仅限研究支持。我们评估风险，不代客操盘。",
    tiers: {
      free: { name: "免费版", cta: null, trial: "第 90 天后，除非订阅" },
      report: { name: "报告版", cta: "订阅", trial: "90 天 Agent 试用结束后可选" },
      briefing: { name: "简报版", cta: "订阅", trial: "90 天 Agent 试用结束后可选" },
      agent: { name: "The Agent", cta: "试用后订阅", trial: "注册起三个月免费，然后免费版" },
    },
    compare_rows: [
      "实时评分（今日）", "报纸版面", "API / JSON接入",
      "类比分辨率（次日/周/月）", "深度类比简报",
      "排名新闻面板", "股票代理 + API密钥",
    ],
    home_cta: "首页 →",
  },
  ms: {
    headline: "3 bulan Agent, kemudian Percuma",
    lead: "Setiap akaun baharu mendapat The Agent percuma selama 3 bulan dari pendaftaran. Tiada caj. Pada hari ke-90 anda turun ke Percuma. Langgan selepas itu jika mahu Report, Briefing, atau Agent. Percubaan tidak bertukar automatik kepada pelan berbayar.",
    compare_title: "Bandingkan pelan",
    compare_lead: "Sokongan penyelidikan sahaja. Kami menilai risiko, bukan berniaga untuk anda.",
    tiers: {
      free: { name: "Percuma", cta: null, trial: "Selepas hari ke-90, melainkan anda langgan" },
      report: { name: "The Report", cta: "Langgan", trial: "Pilihan selepas percubaan Agent 90 hari" },
      briefing: { name: "The Briefing", cta: "Langgan", trial: "Pilihan selepas percubaan Agent 90 hari" },
      agent: { name: "The Agent", cta: "Langgan selepas percubaan", trial: "Percuma 3 bulan, kemudian Percuma" },
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
  const checkout = (cfg.payments && cfg.payments.checkout) || {};
  if (checkout[tierId]) return checkout[tierId];
  const p = cfg.payments?.international || {};
  const map = {
    report: cfg.stripe_report_url || p.stripeReport || p.stripeSubscribe || "/api/billing/checkout?tier=report",
    briefing: cfg.stripe_pro_url || p.stripeBriefing || "/api/billing/checkout?tier=briefing",
    agent: cfg.stripe_api_url || p.stripeAgent || "/api/billing/checkout?tier=agent",
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
  const sep = url.includes("?") ? "&" : "?";
  return `<a class="${cls}" href="${url}${sep}ref=${ref}">${ctaText}</a>`;
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
    const href = tier.href || (payReady(tier.id) ? `${payUrl(tier.id)}${payUrl(tier.id).includes("?") ? "&" : "?"}ref=${ref}` : "");
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
      lead.textContent = d.trial_message;
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
