/** CASSANDRA home dashboard v4  -  score gauge, CRS history, fragility x trigger, watchlist, volatility, fear/greed */

/* Bands mirror src/scoring.py BANDS: Benign <25, Awareness <45, Mania <65, Danger <80, Blow-off. */
const BTHRESH = [0, 25, 45, 65, 80, 100];
const BVARS = ["--band-benign", "--band-awareness", "--band-mania", "--band-danger", "--band-blowoff"];
const UP = "var(--market-up)";
const DOWN = "var(--market-down)";
const TF_FRAMES = ["1D", "5D", "1M"];
const WL_STORAGE = "cassandra-watchlist";
const WL_USER_KEY = "cassandra-user-id";
const HISTORY_LIMIT = 120;
const SVGNS = "http://www.w3.org/2000/svg";

const DEMO = window.CassandraDemo || {};

function apiHeaders(extra) {
  const base = Object.assign({}, extra || {});
  const CC = window.CassandraCommon;
  if (CC && typeof CC.authHeaders === "function") {
    return CC.authHeaders(base);
  }
  return base;
}

const FDATA = {
  en: [
    { t: "API as Ground Truth", d: "Integrate CRS score and factor feeds directly into your models, screeners, and alerts.", cta: "View API docs →", href: "/docs/api" },
    { t: "Build Your AI Agent", d: "Deploy a dedicated agent scoped to your watchlist, a specific sector, or a macro scenario.", cta: "Start building →", href: "/stocks/NOW" },
    { t: "Institutional Data Feed", d: "Real-time options flow, on-chain signals, and dark pool access. Full-tier subscribers only.", cta: "See what's included →", href: "/docs/institutional" },
    { t: "Talk with Our Agents", d: "RAG-grounded chat using today's knowledge graph. Gated  -  only meaningful market questions get through.", cta: "Try the agent →", href: "/agent", chat: true },
  ],
  zh: [
    { t: "API作为基础数据", d: "将CRS评分和因子数据流直接集成到您的模型、筛选器和预警系统中。", cta: "查看API文档 →", href: "/docs/api" },
    { t: "构建您的AI代理", d: "部署专用代理，可针对您的自选股、特定行业或宏观情景进行定制。", cta: "立即开始构建 →", href: "/stocks/NOW" },
    { t: "机构数据订阅", d: "实时期权流、链上信号和暗池访问权限，仅限全级别订阅用户。", cta: "查看包含内容 →", href: "/docs/institutional" },
    { t: "与我们的代理对话", d: "基于今日知识图谱的RAG驱动对话，设有质量门控。", cta: "体验代理 →", href: "/agent", chat: true },
  ],
  ms: [
    { t: "API sebagai Sumber Kebenaran", d: "Integrasi skor CRS dan suapan faktor terus ke dalam model, penyaring, dan amaran anda.", cta: "Lihat dokumen API →", href: "/docs/api" },
    { t: "Bina Ejen AI Anda", d: "Sebarkan ejen khusus yang dilingkupkan kepada senarai pantau, sektor tertentu, atau senario makro.", cta: "Mula bina →", href: "/stocks/NOW" },
    { t: "Suapan Data Institusi", d: "Aliran opsyen masa nyata, isyarat on-chain, dan akses kumpulan gelap. Pelanggan peringkat penuh sahaja.", cta: "Lihat kandungan →", href: "/docs/institutional" },
    { t: "Bercakap dengan Ejen Kami", d: "Sembang RAG berasaskan graf pengetahuan hari ini. Bergerik, hanya soalan pasaran bermakna yang lulus.", cta: "Cuba ejen →", href: "/agent", chat: true },
  ],
};

const WL_PRESET = ["LEU", "NVDA", "MSFT", "AMZN", "TSM", "MU", "AMD", "AVGO", "SMCI", "ARM", "WDC", "NOW", "GOOGL", "META", "CRWD"];


const T = {
  en: {
    ed: "Late City Edition", cov: "Data coverage: {p}%", analog: "Today feels like {d}",
    desk: "Global Market Desk", hwl: "Watchlist", editwl: "Edit", hsi: "Score Inputs",
    read: "Read today's full edition →", edbtn: "Morning edition", hvol: "Top Volatility",
    hfg: "Fear & Greed", hidx: "Index Snapshot", fcHead: "Platform",
    fpub: "Cassandra Research Desk · crash.netie.ai", fdisc: "For decision support only. Not financial advice.",
    wlTitle: "Edit watchlist", wlHint: "Pick tickers below or search to add.",
    siTrigger: "Trigger", siFrag: "Fragility", siCapex: "Capex NLP",
    fgFear: "Fear", fgGreed: "Greed", fgNeutral: "Neutral",
    bands: ["Benign", "Awareness", "Mania", "Danger", "Blow-off"],
    lvlHigh: "high", lvlElevated: "elevated", lvlModerate: "moderate", lvlCut: "cut signal", lvlNoCut: "no cut yet",
    lvlNoData: "not connected",
    tagline: "The daily crash-risk desk",
    scTitle: "Crash Risk Score", asof: "as of {d}", of100: "of 100",
    lblRange: "Confidence range", lblConf: "Model confidence", lblMom: "Momentum",
    mom: { loading: "Loading · fragility rising", plateau: "Plateau · little change", bleeding: "Bleeding · fragility easing" },
    phaseConf: "{p}% conf",
    covNote: "Low data coverage ({p}%): most factors are at neutral defaults until more data sources are connected.",
    scoreErr: "Score unavailable. The score service did not respond, so no number is shown.",
    histTitle: "CRS history", histSub: "0–100, one reading per day",
    ftTitle: "Fragility × Trigger", ftSub: "0–1 each; today's reading and its path",
    histBuilds: "History builds daily from {d}.",
    histSince: "{n} daily readings since {d}.",
    histErr: "History unavailable. The history service did not respond.",
    histEmpty: "No scores recorded yet.",
    ftNeutral: "Both read 0.50, the neutral midpoint.",
    tableSum: "Score history as a table",
    colDate: "Date", colCrs: "CRS", colBand: "Band", colF: "Fragility", colT: "Trigger", colConf: "Confidence",
    qHH: "Fragile & triggered", qHL: "Fragile, no spark", qLH: "Spark, sturdy base", qLL: "Sturdy & calm",
    axF: "Fragility →", axT: "Trigger →", today: "Today",
    sample: "Sample", demo: "Demo",
    fgProxy: "Crypto Fear & Greed proxy · alternative.me",
    fgSample: "Sample reading; the live index is unavailable.",
    fgNone: "Unavailable",
    noTickers: "No tickers.",
    plate: "Plate I.", heroCap: "The seer over the tape: a long rise, and the break she warned of.",
    hlBand: "Crash risk sits in the {b} band",
    summary: (s) => `The Crash Risk Score reads ${s.crs} of 100, in the ${s.band} band (confidence range ${s.lo}–${s.hi}). Fragility is ${s.f} and trigger ${s.t}; momentum: ${s.mom}.`,
    summaryCov: (p) => `Only ${p}% of inputs are live today, so several factors sit at neutral defaults and the reading should be treated as provisional.`,
  },
  zh: {
    ed: "晚城版", cov: "数据覆盖率：{p}%", analog: "今日情势令人想起 {d}",
    desk: "全球市场观察台", hwl: "自选股", editwl: "编辑", hsi: "评分输入",
    read: "阅读今日完整版 →", edbtn: "早版", hvol: "高波动排行",
    hfg: "恐慌贪婪指数", hidx: "指数速览", fcHead: "平台功能",
    fpub: "Cassandra 研究台 · crash.netie.ai", fdisc: "仅供决策支持，非投资建议。",
    wlTitle: "编辑自选股", wlHint: "点击下方代码或搜索添加。",
    siTrigger: "触发器", siFrag: "脆弱性", siCapex: "资本支出 NLP",
    fgFear: "恐慌", fgGreed: "贪婪", fgNeutral: "中性",
    bands: ["良性", "警觉", "狂热", "危险", "爆顶"],
    lvlHigh: "偏高", lvlElevated: "抬升", lvlModerate: "中等", lvlCut: "削减信号", lvlNoCut: "尚无削减",
    lvlNoData: "未接入",
    tagline: "每日崩盘风险观察台",
    scTitle: "崩盘风险评分", asof: "截至 {d}", of100: "满分 100",
    lblRange: "置信区间", lblConf: "模型置信度", lblMom: "动量",
    phases: { accumulation: "吸筹", distribution: "派发", distribution_range: "派发区间", markup: "拉升", markdown: "下跌", undetermined: "未定" },
    mom: { loading: "累积 · 脆弱性上升", plateau: "平台 · 变化不大", bleeding: "释放 · 脆弱性回落" },
    phaseConf: "置信度 {p}%",
    covNote: "数据覆盖率偏低（{p}%）：在接入更多数据源之前，大部分因子取中性默认值。",
    scoreErr: "评分暂不可用：评分服务未响应，因此不显示数字。",
    histTitle: "CRS 历史", histSub: "0–100，每日一个读数",
    ftTitle: "脆弱性 × 触发器", ftSub: "各为 0–1；今日读数及其路径",
    histBuilds: "历史数据自 {d} 起每日累积。",
    histSince: "自 {d} 起共 {n} 个每日读数。",
    histErr: "历史数据暂不可用：历史服务未响应。",
    histEmpty: "尚无评分记录。",
    ftNeutral: "两者均为 0.50，即中性中点。",
    tableSum: "以表格查看评分历史",
    colDate: "日期", colCrs: "CRS", colBand: "区间", colF: "脆弱性", colT: "触发器", colConf: "置信度",
    qHH: "脆弱且已触发", qHL: "脆弱，尚无火花", qLH: "有火花，底子稳", qLL: "稳健平静",
    axF: "脆弱性 →", axT: "触发器 →", today: "今日",
    sample: "示例", demo: "演示",
    fgProxy: "加密货币恐慌贪婪指数代理 · alternative.me",
    fgSample: "示例读数：实时指数不可用。",
    fgNone: "不可用",
    noTickers: "暂无代码。",
    plate: "图版 I。", heroCap: "预言者俯瞰行情：长久的上涨，以及她所警示的崩落。",
    hlBand: "崩盘风险处于「{b}」区间",
    summary: (s) => `崩盘风险评分为 ${s.crs}（满分 100），处于「${s.band}」区间（置信区间 ${s.lo}–${s.hi}）。脆弱性 ${s.f}，触发器 ${s.t}；动量：${s.mom}。`,
    summaryCov: (p) => `今日仅 ${p}% 的输入为实时数据，多项因子取中性默认值，读数应视为初步结果。`,
  },
  ms: {
    ed: "Edisi Kota Lewat", cov: "Liputan data: {p}%", analog: "Hari ini terasa seperti {d}",
    desk: "Meja Pasaran Global", hwl: "Senarai Pantau", editwl: "Edit", hsi: "Input Skor",
    read: "Baca edisi penuh hari ini →", edbtn: "Edisi pagi", hvol: "Volatiliti Tertinggi",
    hfg: "Takut & Tamak", hidx: "Gambaran Indeks", fcHead: "Platform",
    fpub: "Meja Penyelidikan Cassandra · crash.netie.ai", fdisc: "Sokongan keputusan sahaja. Bukan nasihat kewangan.",
    wlTitle: "Edit senarai pantau", wlHint: "Pilih ticker di bawah atau cari untuk tambah.",
    siTrigger: "Pencetus", siFrag: "Kerapuhan", siCapex: "NLP Capex",
    fgFear: "Takut", fgGreed: "Tamak", fgNeutral: "Neutral",
    bands: ["Jinak", "Kesedaran", "Mania", "Bahaya", "Letupan"],
    lvlHigh: "tinggi", lvlElevated: "meningkat", lvlModerate: "sederhana", lvlCut: "isyarat potong", lvlNoCut: "belum potong",
    lvlNoData: "belum disambung",
    tagline: "Meja risiko kejatuhan harian",
    scTitle: "Skor Risiko Kejatuhan", asof: "setakat {d}", of100: "daripada 100",
    lblRange: "Julat keyakinan", lblConf: "Keyakinan model", lblMom: "Momentum",
    phases: { accumulation: "Pengumpulan", distribution: "Pengedaran", distribution_range: "Julat pengedaran", markup: "Kenaikan", markdown: "Penurunan", undetermined: "Belum ditentukan" },
    mom: { loading: "Memuat · kerapuhan meningkat", plateau: "Mendatar · sedikit perubahan", bleeding: "Menyusut · kerapuhan reda" },
    phaseConf: "{p}% yakin",
    covNote: "Liputan data rendah ({p}%): kebanyakan faktor berada pada nilai lalai neutral sehingga lebih banyak sumber data disambungkan.",
    scoreErr: "Skor tidak tersedia. Perkhidmatan skor tidak memberi respons, jadi tiada nombor dipaparkan.",
    histTitle: "Sejarah CRS", histSub: "0–100, satu bacaan sehari",
    ftTitle: "Kerapuhan × Pencetus", ftSub: "0–1 setiap satu; bacaan hari ini dan laluannya",
    histBuilds: "Sejarah dibina setiap hari sejak {d}.",
    histSince: "{n} bacaan harian sejak {d}.",
    histErr: "Sejarah tidak tersedia. Perkhidmatan sejarah tidak memberi respons.",
    histEmpty: "Belum ada skor direkodkan.",
    ftNeutral: "Kedua-duanya 0.50, titik tengah neutral.",
    tableSum: "Sejarah skor sebagai jadual",
    colDate: "Tarikh", colCrs: "CRS", colBand: "Jalur", colF: "Kerapuhan", colT: "Pencetus", colConf: "Keyakinan",
    qHH: "Rapuh & tercetus", qHL: "Rapuh, tiada percikan", qLH: "Percikan, asas kukuh", qLL: "Kukuh & tenang",
    axF: "Kerapuhan →", axT: "Pencetus →", today: "Hari ini",
    sample: "Sampel", demo: "Demo",
    fgProxy: "Proksi Takut & Tamak kripto · alternative.me",
    fgSample: "Bacaan sampel; indeks langsung tidak tersedia.",
    fgNone: "Tidak tersedia",
    noTickers: "Tiada ticker.",
    plate: "Plat I.", heroCap: "Si peramal di atas pita harga: kenaikan panjang, dan kejatuhan yang diamarkannya.",
    hlBand: "Risiko kejatuhan berada dalam jalur {b}",
    summary: (s) => `Skor Risiko Kejatuhan ialah ${s.crs} daripada 100, dalam jalur ${s.band} (julat keyakinan ${s.lo}–${s.hi}). Kerapuhan ${s.f} dan pencetus ${s.t}; momentum: ${s.mom}.`,
    summaryCov: (p) => `Hanya ${p}% input adalah langsung hari ini, jadi beberapa faktor berada pada nilai lalai neutral dan bacaan ini perlu dianggap sementara.`,
  },
};

const CC = window.CassandraCommon || {};
let currentLang = "en";
let curTF = "1D";
let volScale = 14;
let lastAsof = null;

/** Data state: null = not loaded yet, false = request failed, otherwise payload. */
const STATE = { score: null, history: null, hi: null };

function tx(key) {
  return T[currentLang]?.[key] ?? T.en[key] ?? key;
}

function fmt(str, vars) {
  return String(str).replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] != null ? vars[k] : ""));
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function locale() {
  return currentLang === "zh" ? "zh-CN" : currentLang === "ms" ? "ms-MY" : "en-US";
}

function parseDay(asof) {
  return new Date(String(asof).slice(0, 10) + "T12:00:00");
}

function fmtDay(asof, opts) {
  if (!asof) return "";
  return parseDay(asof).toLocaleDateString(locale(), opts || { month: "short", day: "numeric", year: "numeric" });
}

function userId() {
  try {
    let id = localStorage.getItem(WL_USER_KEY);
    if (!id) {
      id = "local-" + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(WL_USER_KEY, id);
    }
    return id;
  } catch (_) {
    return "local";
  }
}

function bandIndex(crs) {
  for (let i = BTHRESH.length - 2; i >= 0; i--) {
    if (crs >= BTHRESH[i]) return i;
  }
  return 0;
}

function bandVar(i) {
  return `var(${BVARS[Math.max(0, Math.min(BVARS.length - 1, i))]})`;
}

function bandName(crs) {
  return tx("bands")[bandIndex(crs)];
}

function renderScale(crs) {
  const idx = bandIndex(crs);
  return `<div class="scale-labels">${tx("bands").map((b, i) =>
    `<span class="${i === idx ? "on" : ""}"><i style="background:${bandVar(i)}"></i>${esc(b)}</span>`
  ).join("")}</div>`;
}

function fmtPct(pct) {
  const up = pct >= 0;
  return { up, color: up ? UP : DOWN, text: `${up ? "+" : ""}${Number(pct).toFixed(2)}%` };
}

function spark(d, w, h, c, lbl) {
  if (!d?.length || d.length < 2) return "";
  const mn = Math.min(...d);
  const mx = Math.max(...d);
  const rng = mx - mn || 1;
  const pts = d.map((v, i) => `${((i / (d.length - 1)) * w).toFixed(1)},${(h - ((v - mn) / rng) * (h - 2) - 1).toFixed(1)}`).join(" ");
  return `<svg role="img" aria-label="${esc(lbl)}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" class="spark"><polyline points="${pts}" fill="none" style="stroke:${c}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el && text != null) el.textContent = text;
}

function show(id, on) {
  const el = document.getElementById(id);
  if (el) el.hidden = !on;
}

function applyLang() {
  const t = T[currentLang];
  const ids = {
    "h-ed": t.ed, "desk-l": t.desk,
    "h-wl": t.hwl, "edit-wl": t.editwl, "h-si": t.hsi, "read-l": t.read,
    "ed-btn": t.edbtn, "h-vol": t.hvol, "h-fg": t.hfg, "h-idx": t.hidx, "fc-head": t.fcHead,
    "f-pub": t.fpub, "f-disc": t.fdisc, "wl-modal-title": t.wlTitle, "wl-modal-hint": t.wlHint,
    "mast-tag": t.tagline, "sc-title": t.scTitle, "lbl-range": t.lblRange, "lbl-conf": t.lblConf, "lbl-mom": t.lblMom,
    "ch-hist-title": t.histTitle, "ch-hist-sub": t.histSub, "ch-ft-title": t.ftTitle, "ch-ft-sub": t.ftSub,
    "hist-table-sum": t.tableSum, "hero-plate": t.plate, "hero-cap-t": t.heroCap,
  };
  Object.keys(ids).forEach((id) => setText(id, ids[id]));
  document.querySelectorAll(".demo-tag").forEach((el) => {
    el.textContent = el.classList.contains("demo-tag-inline") ? t.demo : t.sample;
  });
  setDateLine(lastAsof);
  renderAllScore();
  renderFeats();
  if (window.setAnalogLang) window.setAnalogLang(currentLang);
  try { window.dispatchEvent(new CustomEvent("cassandra:lang", { detail: { lang: currentLang } })); } catch (_) { /* ignore */ }
}

function renderFeats() {
  const fg = document.getElementById("feat-grid");
  if (!fg) return;
  fg.innerHTML = FDATA[currentLang].map((f) => `
    <div class="feat-card">
      <div class="feat-card-title">${f.t}</div>
      <div class="feat-card-body">${f.d}</div>
      ${f.chat ? `<div class="agent-chat-row" id="agent-chat">
        <input type="text" id="agent-input" placeholder="Ask about the market..." aria-label="Agent question"/>
        <button type="button" id="agent-send">→</button>
      </div>
      <div id="agent-reply" class="agent-reply" hidden></div>` : ""}
      <a href="${f.href}" class="home-link feat-cta">${f.cta}</a>
    </div>`).join("");
  document.getElementById("agent-send")?.addEventListener("click", sendAgent);
  document.getElementById("agent-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendAgent();
  });
}

async function sendAgent() {
  const input = document.getElementById("agent-input");
  const reply = document.getElementById("agent-reply");
  if (!input || !reply) return;
  const msg = input.value.trim();
  if (!msg) return;
  reply.hidden = false;
  reply.textContent = "Thinking…";
  try {
    const r = await fetch("/api/agent/chat", {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message: msg }),
    });
    const d = await r.json();
    reply.textContent = d.reply || d.response || "No response.";
  } catch (_) {
    reply.textContent = "Agent unavailable offline.";
  }
}


/* ───────────────────────── score card + charts (plain SVG, no deps) ───────────────────────── */

function n2(v) { return Number(v).toFixed(2); }
function n1(v) { return Number(v).toFixed(1); }
function r2(v) { return Math.round(v * 100) / 100; }

function emptyState(msg, kind) {
  return `<div class="chart-empty${kind === "error" ? " is-error" : ""}" role="status"><span class="chart-empty-mark" aria-hidden="true">${kind === "error" ? "!" : "·"}</span><span>${esc(msg)}</span></div>`;
}

function polar(cx, cy, r, v) {
  const a = Math.PI * (1 - Math.max(0, Math.min(100, v)) / 100);
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}

function arcPath(cx, cy, r, v0, v1) {
  const [x0, y0] = polar(cx, cy, r, v0);
  const [x1, y1] = polar(cx, cy, r, v1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function gaugeSvg(s) {
  const W = 320, H = 190, cx = 160, cy = 170, r = 128, sw = 14;
  const crs = Number(s.crs);
  const idx = bandIndex(crs);
  const hw = s.band_halfwidth != null ? Number(s.band_halfwidth) : null;
  const parts = [];
  for (let i = 0; i < BTHRESH.length - 1; i++) {
    const v0 = BTHRESH[i] + (i ? 0.45 : 0);
    const v1 = BTHRESH[i + 1] - (i < BTHRESH.length - 2 ? 0.45 : 0);
    parts.push(`<path d="${arcPath(cx, cy, r, v0, v1)}" fill="none" stroke-width="${sw}" style="stroke:${bandVar(i)}" opacity="${i === idx ? 1 : 0.28}"/>`);
  }
  // threshold numerals just inside the arc
  BTHRESH.forEach((v) => {
    const [x, y] = polar(cx, cy, r - sw / 2 - 10, v);
    const anchor = v === 0 ? "start" : v === 100 ? "end" : "middle";
    const dy = v === 0 || v === 100 ? 0 : 3;
    parts.push(`<text x="${x.toFixed(1)}" y="${(y + dy).toFixed(1)}" text-anchor="${anchor}" class="ch-axis">${v}</text>`);
  });
  // confidence range: crs ± band_halfwidth, drawn just outside the arc
  if (hw != null && hw > 0) {
    const ro = r + sw / 2 + 6;
    const lo = Math.max(0, crs - hw), hi = Math.min(100, crs + hw);
    parts.push(`<path d="${arcPath(cx, cy, ro, lo, hi)}" fill="none" class="g-ci" stroke-width="3" stroke-linecap="butt"/>`);
    [lo, hi].forEach((v) => {
      const [x0, y0] = polar(cx, cy, ro - 4, v);
      const [x1, y1] = polar(cx, cy, ro + 4, v);
      parts.push(`<line x1="${x0.toFixed(1)}" y1="${y0.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${y1.toFixed(1)}" class="g-ci" stroke-width="1.5"/>`);
    });
  }
  // marker across the band at today's score
  const [mx0, my0] = polar(cx, cy, r - sw / 2 - 5, crs);
  const [mx1, my1] = polar(cx, cy, r + sw / 2 + 2, crs);
  parts.push(`<line x1="${mx0.toFixed(1)}" y1="${my0.toFixed(1)}" x2="${mx1.toFixed(1)}" y2="${my1.toFixed(1)}" class="ch-ring" stroke-width="7" stroke-linecap="round"/>`);
  parts.push(`<line x1="${mx0.toFixed(1)}" y1="${my0.toFixed(1)}" x2="${mx1.toFixed(1)}" y2="${my1.toFixed(1)}" class="ch-ink" stroke-width="3" stroke-linecap="round"/>`);
  parts.push(`<text x="${cx}" y="${cy - 30}" text-anchor="middle" class="g-num">${n1(crs)}</text>`);
  parts.push(`<text x="${cx}" y="${cy - 8}" text-anchor="middle" class="g-of">${esc(tx("of100"))}</text>`);
  const label = `${tx("scTitle")} ${n1(crs)} ${tx("of100")}, ${bandName(crs)}` +
    (hw != null ? `, ${tx("lblRange")} ${n1(crs - hw)}–${n1(crs + hw)}` : "");
  return `<svg class="gauge-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${parts.join("")}</svg>`;
}

function phaseColor(raw) {
  const p = String(raw || "").toLowerCase();
  if (p.includes("distribution") || p.includes("markdown") || p.includes("climax")) return "var(--color-danger)";
  if (p.includes("aware") || p.includes("upthrust") || p.includes("undetermined")) return "var(--color-warn)";
  if (p.includes("accumulation") || p.includes("secondary")) return "var(--color-neutral)";
  if (p.includes("markup")) return "var(--color-ok)";
  return "var(--color-warn)";
}

function renderPhase(score) {
  const labelEl = document.getElementById("phase-label");
  const confEl = document.getElementById("phase-conf");
  if (!labelEl || !confEl) return;
  if (!score?.phase) {
    labelEl.textContent = "";
    confEl.textContent = "";
    return;
  }
  const key = String(score.phase).toLowerCase();
  const label = (tx("phases") || {})[key] || String(score.phase).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  labelEl.innerHTML = `<i class="phase-dot" style="background:${phaseColor(score.phase)}"></i>${esc(label)}`;
  const conf = score.phase_confidence;
  confEl.textContent = conf != null ? fmt(tx("phaseConf"), { p: Math.round(conf * 100) }) : "";
}

function renderScoreCard() {
  const s = STATE.score;
  const g = document.getElementById("crs-gauge");
  if (!g || s === null) return;
  const cov = document.getElementById("cov-note");
  if (!s) {
    g.innerHTML = emptyState(tx("scoreErr"), "error");
    show("score-facts", false);
    if (cov) cov.hidden = true;
    setText("sc-asof", "");
    setText("h-cov", "");
    return;
  }
  const crs = Number(s.crs);
  g.innerHTML = gaugeSvg(s);
  show("score-facts", true);
  const bEl = document.getElementById("bname");
  if (bEl) bEl.innerHTML = `<i class="swatch" style="background:${bandVar(bandIndex(crs))}"></i>${esc(bandName(crs))}`;
  renderPhase(s);
  const hw = s.band_halfwidth != null ? Number(s.band_halfwidth) : null;
  setText("band-range", hw != null ? `${n1(crs - hw)} – ${n1(crs + hw)}  (±${n1(hw)})` : "–");
  setText("conf-val", s.confidence != null ? `${Math.round(Number(s.confidence) * 100)}%` : "–");
  const mom = s.momentum_state ? (tx("mom")[s.momentum_state] || String(s.momentum_state)) : "–";
  setText("mom-val", mom);
  const scale = document.getElementById("bscale");
  if (scale) scale.innerHTML = renderScale(crs);
  setText("sc-asof", s.asof ? fmt(tx("asof"), { d: fmtDay(s.asof) }) : "");
  const covPct = s.coverage != null ? Math.round(Number(s.coverage) * 100) : null;
  setText("h-cov", covPct != null ? fmt(tx("cov"), { p: covPct }) : "");
  if (cov) {
    const low = covPct != null && Number(s.coverage) < 0.5;
    cov.hidden = !low;
    if (low) cov.textContent = fmt(tx("covNote"), { p: covPct });
  }
}

/** History rows oldest → newest, deduplicated by date. Falls back to today's score only if history is empty. */
function histRows() {
  const seen = new Set();
  let rows = Array.isArray(STATE.history) ? STATE.history.filter((r) => r && r.asof && r.crs != null) : [];
  rows = rows.slice().sort((a, b) => String(a.asof).localeCompare(String(b.asof)))
    .filter((r) => (seen.has(r.asof) ? false : seen.add(r.asof)));
  const s = STATE.score;
  if (!rows.length && Array.isArray(STATE.history) && s && s.crs != null && s.asof) {
    rows = [{ asof: s.asof, crs: s.crs, band: s.band, fragility: s.fragility, trigger: s.trigger, confidence: s.confidence }];
  }
  return rows;
}

function histTipHtml(r) {
  const parts = [`<b>${esc(fmtDay(r.asof))}</b>`, `${esc(tx("colCrs"))} <span class="cm">${n1(r.crs)}</span> · ${esc(bandName(Number(r.crs)))}`];
  if (r.fragility != null || r.trigger != null) {
    parts.push(`${esc(tx("colF"))} <span class="cm">${r.fragility != null ? n2(r.fragility) : "–"}</span> · ${esc(tx("colT"))} <span class="cm">${r.trigger != null ? n2(r.trigger) : "–"}</span>`);
  }
  if (r.confidence != null) parts.push(`${esc(tx("colConf"))} <span class="cm">${Math.round(r.confidence * 100)}%</span>`);
  return parts.join("<br/>");
}

function chartGuard(el, noteId) {
  const note = document.getElementById(noteId);
  if (STATE.history === null) return { stop: true, note };
  if (STATE.history === false) {
    el.innerHTML = emptyState(tx("histErr"), "error");
    if (note) note.hidden = true;
    return { stop: true, note };
  }
  const rows = histRows();
  if (!rows.length) {
    el.innerHTML = emptyState(tx("histEmpty"));
    if (note) note.hidden = true;
    return { stop: true, note };
  }
  return { stop: false, note, rows };
}

function renderHistoryChart() {
  const el = document.getElementById("crs-hist-chart");
  if (!el) return;
  const g = chartGuard(el, "crs-hist-note");
  if (g.stop) return;
  const rows = g.rows;
  const W = Math.max(260, Math.round(el.clientWidth || 560));
  const narrow = W < 460;
  const H = narrow ? 196 : 224;
  const m = { l: 28, r: narrow ? 70 : 84, t: 10, b: 26 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const ys = (v) => m.t + ph * (1 - v / 100);
  const ts = rows.map((r) => parseDay(r.asof).getTime());
  const t0 = Math.min(...ts), t1 = Math.max(...ts);
  const xs = (t) => (rows.length === 1 || t1 === t0 ? m.l + pw / 2 : m.l + pw * ((t - t0) / (t1 - t0)));
  const P = [];
  // band zones + right-hand band labels (text inks, colour carried by the swatch)
  for (let i = 0; i < BTHRESH.length - 1; i++) {
    const yTop = ys(BTHRESH[i + 1]), yBot = ys(BTHRESH[i]);
    P.push(`<rect x="${m.l}" y="${yTop.toFixed(1)}" width="${pw}" height="${(yBot - yTop).toFixed(1)}" style="fill:${bandVar(i)}" opacity="0.07"/>`);
    const mid = (yTop + yBot) / 2;
    if (yBot - yTop >= 11) {
      P.push(`<rect x="${m.l + pw + 7}" y="${(mid - 4).toFixed(1)}" width="3" height="8" rx="1" style="fill:${bandVar(i)}"/>`);
      P.push(`<text x="${m.l + pw + 14}" y="${(mid + 3.2).toFixed(1)}" class="ch-lbl">${esc(tx("bands")[i])}</text>`);
    }
  }
  BTHRESH.forEach((v) => {
    const y = ys(v).toFixed(1);
    P.push(`<line x1="${m.l}" x2="${m.l + pw}" y1="${y}" y2="${y}" class="${v === 0 ? "ch-base" : "ch-grid"}"/>`);
    P.push(`<text x="${m.l - 6}" y="${(+y + 3).toFixed(1)}" text-anchor="end" class="ch-axis">${v}</text>`);
  });
  // x labels: first / last (and middle when there is room)
  const xl = [0];
  if (rows.length > 1) xl.push(rows.length - 1);
  if (rows.length >= 5 && pw > 300) xl.splice(1, 0, Math.floor((rows.length - 1) / 2));
  xl.forEach((i, k) => {
    const x = xs(ts[i]);
    const anchor = rows.length === 1 ? "middle" : k === 0 ? "start" : k === xl.length - 1 ? "end" : "middle";
    P.push(`<text x="${x.toFixed(1)}" y="${H - 8}" text-anchor="${anchor}" class="ch-axis">${esc(fmtDay(rows[i].asof, { month: "short", day: "numeric" }))}</text>`);
  });
  const pts = rows.map((r, i) => [xs(ts[i]), ys(Number(r.crs))]);
  if (rows.length > 1) {
    P.push(`<polyline points="${pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")}" class="ch-line" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
  }
  if (rows.length <= 60) {
    pts.slice(0, -1).forEach(([x, y]) => P.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.6" class="ch-dot"/>`));
  }
  // today's confidence range, only when the latest score describes the same day
  const last = rows[rows.length - 1];
  const [lx, ly] = pts[pts.length - 1];
  const s = STATE.score;
  let hwTxt = "";
  if (s && s.asof === last.asof && s.band_halfwidth != null) {
    const hw = Number(s.band_halfwidth);
    const yT = ys(Math.min(100, Number(last.crs) + hw)), yB = ys(Math.max(0, Number(last.crs) - hw));
    P.push(`<rect x="${(lx - 6).toFixed(1)}" y="${yT.toFixed(1)}" width="12" height="${Math.max(1, yB - yT).toFixed(1)}" rx="2" class="ch-ci"/>`);
    hwTxt = ` ±${n1(hw)}`;
  }
  P.push(`<circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="5.5" class="ch-ring-fill" style="fill:${bandVar(bandIndex(Number(last.crs)))}"/>`);
  const lblRight = rows.length === 1 || lx < m.l + pw * 0.75;
  P.push(`<text x="${(lx + (lblRight ? 12 : -12)).toFixed(1)}" y="${(ly - 8).toFixed(1)}" text-anchor="${lblRight ? "start" : "end"}" class="ch-val">${n1(last.crs)}${hwTxt}</text>`);
  // hover layer
  P.push(`<line class="ch-cross" x1="0" x2="0" y1="${m.t}" y2="${m.t + ph}" visibility="hidden"/>`);
  P.push(`<rect class="ch-hit" x="${m.l}" y="${m.t}" width="${pw}" height="${ph}" fill="transparent"/>`);
  const aria = `${tx("histTitle")}: ${rows.map((r) => `${fmtDay(r.asof)} ${n1(r.crs)}`).join("; ")}`;
  el.innerHTML = `<svg class="chart-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(aria)}">${P.join("")}</svg>`;
  const svg = el.querySelector("svg");
  const cross = svg.querySelector(".ch-cross");
  const hit = svg.querySelector(".ch-hit");
  const onMove = (ev) => {
    const box = svg.getBoundingClientRect();
    const x = (ev.clientX - box.left) * (W / box.width);
    let best = 0;
    pts.forEach((p, i) => { if (Math.abs(p[0] - x) < Math.abs(pts[best][0] - x)) best = i; });
    cross.setAttribute("x1", pts[best][0]); cross.setAttribute("x2", pts[best][0]);
    cross.setAttribute("visibility", "visible");
    showTip(ev.clientX, box.top + (pts[best][1] * box.height) / H, histTipHtml(rows[best]));
  };
  hit.addEventListener("pointermove", onMove);
  hit.addEventListener("pointerdown", onMove);
  hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  if (g.note) {
    g.note.hidden = false;
    g.note.textContent = rows.length === 1
      ? fmt(tx("histBuilds"), { d: fmtDay(rows[0].asof) })
      : fmt(tx("histSince"), { n: rows.length, d: fmtDay(rows[0].asof) });
  }
}

function renderFTChart() {
  const el = document.getElementById("ft-chart");
  if (!el) return;
  const g = chartGuard(el, "ft-note");
  if (g.stop) return;
  const rows = g.rows.filter((r) => r.fragility != null && r.trigger != null);
  if (!rows.length) {
    el.innerHTML = emptyState(tx("histEmpty"));
    if (g.note) g.note.hidden = true;
    return;
  }
  const W = Math.max(240, Math.round(el.clientWidth || 340));
  const m = { l: 46, r: 10, t: 8, b: 34 };
  const pw = W - m.l - m.r;
  const ph = Math.round(Math.max(170, Math.min(pw * 0.72, 230)));
  const H = ph + m.t + m.b;
  const xs = (f) => m.l + pw * Math.max(0, Math.min(1, f));
  const ys = (t) => m.t + ph * (1 - Math.max(0, Math.min(1, t)));
  const P = [];
  P.push(`<rect x="${xs(0.5)}" y="${m.t}" width="${pw / 2}" height="${ph / 2}" style="fill:var(--band-danger)" opacity="0.08"/>`);
  P.push(`<rect x="${m.l}" y="${ys(0.5)}" width="${pw / 2}" height="${ph / 2}" style="fill:var(--band-benign)" opacity="0.07"/>`);
  P.push(`<rect x="${m.l}" y="${m.t}" width="${pw}" height="${ph}" fill="none" class="ch-frame"/>`);
  P.push(`<line x1="${xs(0.5)}" x2="${xs(0.5)}" y1="${m.t}" y2="${m.t + ph}" class="ch-mid"/>`);
  P.push(`<line x1="${m.l}" x2="${m.l + pw}" y1="${ys(0.5)}" y2="${ys(0.5)}" class="ch-mid"/>`);
  const qp = 7;
  P.push(`<text x="${m.l + qp}" y="${m.t + 14}" class="ch-q">${esc(tx("qLH"))}</text>`);
  P.push(`<text x="${m.l + pw - qp}" y="${m.t + 14}" text-anchor="end" class="ch-q">${esc(tx("qHH"))}</text>`);
  P.push(`<text x="${m.l + qp}" y="${m.t + ph - 8}" class="ch-q">${esc(tx("qLL"))}</text>`);
  P.push(`<text x="${m.l + pw - qp}" y="${m.t + ph - 8}" text-anchor="end" class="ch-q">${esc(tx("qHL"))}</text>`);
  [0, 0.5, 1].forEach((v) => {
    const anchor = v === 0 ? "start" : v === 1 ? "end" : "middle";
    P.push(`<text x="${xs(v)}" y="${m.t + ph + 13}" text-anchor="${anchor}" class="ch-axis">${v.toFixed(1)}</text>`);
    P.push(`<text x="${m.l - 5}" y="${(ys(v) + (v === 1 ? 8 : v === 0 ? -2 : 3)).toFixed(1)}" text-anchor="end" class="ch-axis">${v.toFixed(1)}</text>`);
  });
  P.push(`<text x="${m.l + pw}" y="${H - 4}" text-anchor="end" class="ch-lbl">${esc(tx("axF"))}</text>`);
  P.push(`<text transform="translate(11 ${m.t + ph}) rotate(-90)" class="ch-lbl">${esc(tx("axT"))}</text>`);
  const pts = rows.map((r) => [xs(Number(r.fragility)), ys(Number(r.trigger))]);
  if (pts.length > 1) {
    P.push(`<polyline points="${pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")}" class="ch-trail" fill="none" stroke-width="1.25" stroke-linejoin="round"/>`);
    pts.slice(0, -1).forEach(([x, y], i) => {
      P.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.6" class="ch-trail-dot" opacity="${(0.35 + 0.65 * (i / pts.length)).toFixed(2)}"/>`);
    });
  }
  const last = rows[rows.length - 1];
  const [lx, ly] = pts[pts.length - 1];
  P.push(`<circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="6.5" class="ch-ring-fill ch-today"/>`);
  const right = lx < m.l + pw * 0.62;
  const up = ly > m.t + 36;
  P.push(`<text x="${(lx + (right ? 11 : -11)).toFixed(1)}" y="${(ly + (up ? -10 : 18)).toFixed(1)}" text-anchor="${right ? "start" : "end"}" class="ch-val ch-halo">${esc(tx("today"))} · ${n2(last.fragility)} / ${n2(last.trigger)}</text>`);
  pts.forEach(([x, y], i) => P.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="13" fill="transparent" class="ch-pt-hit" data-i="${i}"/>`));
  const aria = `${tx("ftTitle")}: ${rows.map((r) => `${fmtDay(r.asof)} ${tx("colF")} ${n2(r.fragility)}, ${tx("colT")} ${n2(r.trigger)}`).join("; ")}`;
  el.innerHTML = `<svg class="chart-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(aria)}">${P.join("")}</svg>`;
  el.querySelectorAll(".ch-pt-hit").forEach((c) => {
    const on = (ev) => {
      const box = c.getBoundingClientRect();
      showTip(box.left + box.width / 2, box.top + box.height / 2, histTipHtml(rows[Number(c.dataset.i)]));
      ev.stopPropagation();
    };
    c.addEventListener("pointerenter", on);
    c.addEventListener("pointerdown", on);
    c.addEventListener("pointerleave", hideTip);
  });
  if (g.note) {
    const bits = [];
    if (rows.length === 1) bits.push(fmt(tx("histBuilds"), { d: fmtDay(rows[0].asof) }));
    else bits.push(fmt(tx("histSince"), { n: rows.length, d: fmtDay(rows[0].asof) }));
    if (r2(last.fragility) === 0.5 && r2(last.trigger) === 0.5) bits.push(tx("ftNeutral"));
    g.note.hidden = false;
    g.note.textContent = bits.join(" ");
  }
}

function renderHistTable() {
  const wrap = document.getElementById("hist-table-wrap");
  const box = document.getElementById("hist-table");
  if (!wrap || !box) return;
  const rows = Array.isArray(STATE.history) ? histRows() : [];
  wrap.hidden = !rows.length;
  if (!rows.length) return;
  const cell = (v, d) => (v == null ? "–" : d(v));
  box.innerHTML = `<table class="hist-table"><thead><tr>
    <th scope="col">${esc(tx("colDate"))}</th><th scope="col">${esc(tx("colCrs"))}</th><th scope="col">${esc(tx("colBand"))}</th>
    <th scope="col">${esc(tx("colF"))}</th><th scope="col">${esc(tx("colT"))}</th><th scope="col">${esc(tx("colConf"))}</th>
  </tr></thead><tbody>${rows.slice().reverse().map((r) => `<tr>
    <td>${esc(fmtDay(r.asof))}</td><td class="cm">${n1(r.crs)}</td><td>${esc(bandName(Number(r.crs)))}</td>
    <td class="cm">${cell(r.fragility, n2)}</td><td class="cm">${cell(r.trigger, n2)}</td>
    <td class="cm">${cell(r.confidence, (v) => Math.round(v * 100) + "%")}</td></tr>`).join("")}</tbody></table>`;
}

function showTip(x, y, html) {
  const tip = document.getElementById("chart-tip");
  if (!tip) return;
  tip.innerHTML = html;
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let left = x + 14, top = y - h - 10;
  if (left + w > window.innerWidth - 8) left = x - w - 14;
  if (left < 8) left = 8;
  if (top < 8) top = y + 14;
  tip.style.left = `${Math.round(left)}px`;
  tip.style.top = `${Math.round(top)}px`;
}

function hideTip() {
  const tip = document.getElementById("chart-tip");
  if (tip) tip.hidden = true;
}

function renderScoreInputs(score) {
  const el = document.getElementById("si-rows");
  if (!el) return;
  if (!score) { el.innerHTML = ""; return; }
  const capex = score.capex_cut_nlp ?? score.extra?.capex_cut_nlp;
  const rows = [
    { n: tx("siTrigger"), v: score.trigger != null ? n2(score.trigger) : "–", lbl: score.trigger != null ? labelLevel(score.trigger) : tx("lvlNoData") },
    { n: tx("siFrag"), v: score.fragility != null ? n2(score.fragility) : "–", lbl: score.fragility != null ? labelLevel(score.fragility) : tx("lvlNoData") },
    { n: tx("siCapex"), v: capex != null ? n2(capex) : "–", lbl: capex == null ? tx("lvlNoData") : Number(capex) > 0.5 ? tx("lvlCut") : tx("lvlNoCut") },
  ];
  el.innerHTML = rows.map((r) => `<div class="rb home-si-row">
    <span class="home-si-name">${esc(r.n)}</span>
    <span class="cm home-si-val">${r.v}</span>
    <span class="home-si-lbl">${esc(r.lbl)}</span>
  </div>`).join("");
}

function labelLevel(v) {
  if (v == null) return "-";
  const n = Number(v);
  if (n >= 0.65) return tx("lvlHigh");
  if (n >= 0.45) return tx("lvlElevated");
  return tx("lvlModerate");
}

function populateNarrative() {
  const s = STATE.score || null;
  const hi = STATE.hi || null;
  // The analog line is only shown when the edition carries an analog date backed by sourced analog news.
  const analogOk = !!(hi && hi.analog_date && Array.isArray(hi.analog_news) && hi.analog_news.length);
  show("analog-row", analogOk);
  if (analogOk) setText("analog-t", fmt(tx("analog"), { d: hi.analog_date }));
  let headline = "";
  if (hi?.headline && currentLang === "en") headline = hi.headline;
  else if (s && s.crs != null) headline = fmt(tx("hlBand"), { b: bandName(Number(s.crs)) });
  setText("hl", headline);
  if (s && s.crs != null) {
    const crs = Number(s.crs);
    const hw = s.band_halfwidth != null ? Number(s.band_halfwidth) : 0;
    setText("bp1", tx("summary")({
      crs: n1(crs), band: bandName(crs), lo: n1(crs - hw), hi: n1(crs + hw),
      f: s.fragility != null ? n2(s.fragility) : "–", t: s.trigger != null ? n2(s.trigger) : "–",
      mom: s.momentum_state ? (tx("mom")[s.momentum_state] || s.momentum_state) : "–",
    }));
    setText("bp2", s.coverage != null && Number(s.coverage) < 0.5 ? tx("summaryCov")(Math.round(Number(s.coverage) * 100)) : "");
  } else {
    setText("bp1", "");
    setText("bp2", "");
  }
}

function renderAllScore() {
  renderScoreCard();
  renderScoreInputs(STATE.score || null);
  populateNarrative();
  renderHistoryChart();
  renderFTChart();
  renderHistTable();
}

function setDateLine(asof) {
  const el = document.getElementById("cdate");
  if (!el) return;
  const d = asof ? parseDay(asof) : new Date();
  el.textContent = d.toLocaleDateString(locale(), {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }).toUpperCase();
}

/* ───────────────────────── side panels ───────────────────────── */

function renderWatchlist(rows, isSample) {
  const el = document.getElementById("wl-tbl");
  if (!el) return;
  show("wl-demo", !!isSample || (rows || []).some((r) => /demo|sample|seed/i.test(String(r.source || ""))));
  if (!rows?.length) {
    el.innerHTML = `<div class="home-empty">${esc(tx("noTickers"))}</div>`;
    return;
  }
  el.innerHTML = rows.map((r) => {
    const { color, text } = fmtPct(Number(r.pct) || 0);
    const sym = esc(r.sym);
    return `<div class="rb home-pt-row">
      <a href="/stocks/${encodeURIComponent(r.sym)}" class="cm home-pt-sym home-ticker-link">${sym}</a>
      <span class="cm home-pt-px">${esc(r.px ?? "-")}</span>
      <span class="cm home-pt-pct" style="color:${color}">${text}</span>
    </div>`;
  }).join("");
}

function renderVol(movers, isSample) {
  const vr = document.getElementById("vol-rows");
  if (!vr) return;
  show("vol-demo", !!isSample);
  vr.innerHTML = (movers || []).map((r) => {
    const { color, text } = fmtPct(Number(r.pct) || 0);
    const bw = Math.min(100, Math.abs(Number(r.pct) || 0) / volScale * 100).toFixed(1);
    return `<div class="home-mov-row">
      <span class="cm home-mov-sym">${esc(r.sym)}</span>
      <div class="home-mov-bar"><div style="width:${bw}%;background:${color}"></div></div>
      <span class="cm home-mov-pct" style="color:${color}">${text.replace(".00", ".0")}</span>
    </div>`;
  }).join("");
}

function renderIndices(indices, isSample) {
  const ie = document.getElementById("idx-el");
  if (!ie) return;
  show("idx-demo", !!isSample);
  ie.innerHTML = (indices || []).map((r) => {
    const { color, text } = fmtPct(Number(r.pct) || 0);
    return `<div class="home-idx-row">
      <span class="cm home-idx-sym">${esc(r.sym)}</span>
      <span class="cm home-idx-val">${esc(r.val ?? "-")}</span>
      ${spark(r.spark || r.d, 42, 15, color, r.sym)}
      <span class="cm home-idx-pct" style="color:${color}">${text}</span>
    </div>`;
  }).join("");
}

function fgLabelText(label) {
  const l = String(label || "").toLowerCase();
  if (l.includes("fear")) return tx("fgFear");
  if (l.includes("greed")) return tx("fgGreed");
  return tx("fgNeutral");
}

function fgColor(value) {
  const v = Number(value);
  if (v < 45) return DOWN;
  if (v > 55) return UP;
  return "var(--color-text-secondary)";
}

function renderFearGreed(fg, isSample) {
  const val = document.getElementById("fg-val");
  const lbl = document.getElementById("fg-label");
  const sp = document.getElementById("fg-spark");
  const src = document.getElementById("fg-src");
  if (!fg || fg.value == null) {
    if (val) val.textContent = "";
    if (lbl) { lbl.textContent = tx("fgNone"); lbl.style.color = ""; }
    if (sp) sp.innerHTML = "";
    if (src) src.textContent = "";
    show("fg-demo", false);
    return;
  }
  const sample = !!isSample || /demo/i.test(String(fg.source || ""));
  const c = fgColor(fg.value);
  if (val) { val.textContent = fg.value; val.style.color = c; }
  if (lbl) { lbl.textContent = fgLabelText(fg.label); lbl.style.color = c; }
  if (sp) sp.innerHTML = spark(fg.spark || [], 62, 18, c, tx("hfg"));
  show("fg-demo", sample);
  if (src) src.textContent = sample ? tx("fgSample") : /alternative\.me/.test(String(fg.source || "")) ? tx("fgProxy") : "";
}


/** GET JSON; returns the payload, or false when the request fails / is not JSON. */
async function fetchJSON(url, opts) {
  try {
    const r = await fetch(url, Object.assign({ headers: apiHeaders() }, opts || {}));
    if (!r.ok) return false;
    const ct = r.headers.get("content-type") || "";
    if (!ct.includes("application/json")) return false;
    return await r.json();
  } catch (_) {
    return false;
  }
}

async function loadWatchlist() {
  const uid = userId();
  let tickers = null;
  try {
    const saved = localStorage.getItem(WL_STORAGE);
    if (saved) tickers = JSON.parse(saved);
  } catch (_) { /* ignore */ }
  if (tickers?.length) {
    try {
      await fetch("/api/watchlist/update", {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ user: uid, tickers }),
      });
    } catch (_) { /* offline */ }
  }
  const d = await fetchJSON(`/api/watchlist?user=${encodeURIComponent(uid)}`);
  if (d && d.rows?.length) {
    renderWatchlist(d.rows, false);
    try { localStorage.setItem(WL_STORAGE, JSON.stringify(d.tickers)); } catch (_) { /* ignore */ }
    return d.tickers;
  }
  renderWatchlist(DEMO.watchlist || [], true);
  return tickers || ["LEU", "NVDA", "MSFT", "AMZN", "TSM"];
}

async function saveWatchlist(tickers) {
  const uid = userId();
  try { localStorage.setItem(WL_STORAGE, JSON.stringify(tickers)); } catch (_) { /* ignore */ }
  try {
    const r = await fetch("/api/watchlist/update", {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ user: uid, tickers }),
    });
    if (r.ok) {
      const d = await r.json();
      renderWatchlist(d.rows, false);
    }
  } catch (_) { /* offline */ }
}

async function fetchMovers() {
  const d = await fetchJSON(`/api/movers?tf=${curTF}&sector=tech,semis&limit=10`);
  if (d && d.movers?.length) {
    volScale = d.scale || 14;
    return { movers: d.movers, sample: d.live !== true };
  }
  const pack = DEMO.movers?.[curTF] || DEMO.movers?.["1D"];
  volScale = pack?.scale || 14;
  return { movers: pack?.movers || [], sample: true };
}

async function loadIndices() {
  const d = await fetchJSON("/api/indices");
  if (d && d.indices?.length) {
    // /api/indices has no live flag yet and serves fixed snapshot values; treat as sample unless it says otherwise.
    renderIndices(d.indices, d.live !== true);
    return;
  }
  renderIndices((DEMO.indices || []).map((r) => ({ ...r, spark: demoSpark(r.sym) })), true);
}

function demoSpark(sym) {
  const out = [];
  let v = 50;
  for (let i = 0; i < 20; i++) {
    v += (Math.sin(i + sym.length) - 0.5) * 2;
    out.push(v);
  }
  return out;
}

function cycleTF() {
  curTF = TF_FRAMES[(TF_FRAMES.indexOf(curTF) + 1) % TF_FRAMES.length];
  document.getElementById("tf-btn").textContent = `${curTF} ▸`;
  loadMovers();
}

async function loadMovers() {
  const { movers, sample } = await fetchMovers();
  renderVol(movers, sample);
}

function setupWatchlistModal() {
  const modal = document.getElementById("wl-modal");
  const edit = document.getElementById("edit-wl");
  const search = document.getElementById("wl-search");
  const chipsEl = document.getElementById("wl-chips");
  const selectedEl = document.getElementById("wl-selected");
  const cancel = document.getElementById("wl-cancel");
  let selected = [];

  function renderSelected() {
    if (!selectedEl) return;
    selectedEl.innerHTML = selected.map((s) =>
      `<span class="wl-sel-chip">${s}<button type="button" data-rm="${s}" aria-label="Remove ${s}">×</button></span>`
    ).join("");
    selectedEl.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.onclick = () => {
        selected = selected.filter((x) => x !== btn.dataset.rm);
        renderSelected();
        renderChips(search?.value || "");
      };
    });
  }

  function renderChips(filter) {
    if (!chipsEl) return;
    const q = (filter || "").trim().toUpperCase();
    const list = WL_PRESET.filter((s) => !q || s.includes(q));
    chipsEl.innerHTML = list.map((s) =>
      `<button type="button" class="wl-chip${selected.includes(s) ? " on" : ""}" data-sym="${s}">${s}</button>`
    ).join("");
    chipsEl.querySelectorAll(".wl-chip").forEach((btn) => {
      btn.onclick = () => {
        const sym = btn.dataset.sym;
        if (selected.includes(sym)) selected = selected.filter((x) => x !== sym);
        else if (selected.length < 12) selected.push(sym);
        renderSelected();
        renderChips(search?.value || "");
      };
    });
  }

  edit?.addEventListener("click", async () => {
    const tickers = await loadWatchlist();
    selected = [...(tickers || DEFAULT_WL)];
    renderSelected();
    renderChips("");
    if (search) search.value = "";
    modal?.showModal();
  });
  search?.addEventListener("input", () => renderChips(search.value));
  cancel?.addEventListener("click", () => modal?.close());
  document.getElementById("wl-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selected.length) selected = [...DEFAULT_WL];
    await saveWatchlist(selected);
    modal?.close();
  });
}

const DEFAULT_WL = ["LEU", "NVDA", "MSFT", "AMZN", "TSM"];

function isLocalDev() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}


function setupControls() {
  if (CC.initThemeToggle) CC.initThemeToggle(false);
  if (CC.initAccountMenu) CC.initAccountMenu();
  if (CC.initLangCycle) {
    CC.initLangCycle((lang) => {
      currentLang = T[lang] ? lang : "en";
      applyLang();
    });
  } else {
    currentLang = CC.detectLang ? CC.detectLang() : "en";
    if (!T[currentLang]) currentLang = "en";
    applyLang();
  }
  document.getElementById("tf-btn")?.addEventListener("click", cycleTF);
  let rt = null;
  let lastW = window.innerWidth;
  window.addEventListener("resize", () => {
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(rt);
    rt = setTimeout(() => { renderHistoryChart(); renderFTChart(); }, 120);
  });
  document.addEventListener("scroll", hideTip, { passive: true });
}

function setupRunButton() {
  const btn = document.getElementById("runBtn");
  if (!btn || !isLocalDev()) return;
  btn.classList.add("visible");
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Running…";
    try { await fetch("/api/run", { method: "POST" }); } catch (_) { /* offline */ }
    await refresh();
    btn.disabled = false;
    btn.textContent = "Run cycle";
  };
}

async function refresh() {
  const [latest, hist, hi, fg] = await Promise.all([
    fetchJSON("/api/latest"),
    fetchJSON(`/api/scores/history?limit=${HISTORY_LIMIT}`),
    fetchJSON("/api/report/highlights"),
    fetchJSON("/api/signals/fear_greed"),
  ]);
  let score = latest && latest.crs != null ? latest : false;
  if (!score) {
    const d = await fetchJSON("/api/dashboard");
    if (d && d.score && d.score.crs != null) score = d.score;
  }
  STATE.score = score;
  STATE.history = hist && Array.isArray(hist.history) ? hist.history : false;
  STATE.hi = hi || null;
  lastAsof = (score && score.asof) || STATE.hi?.asof || null;
  setDateLine(lastAsof);
  renderAllScore();
  if (fg && fg.value != null) renderFearGreed(fg, false);
  else renderFearGreed(DEMO.fearGreed || null, true);

  try { await loadWatchlist(); } catch (e) { console.warn("watchlist", e); renderWatchlist(DEMO.watchlist || [], true); }
  try { await loadMovers(); } catch (e) { console.warn("movers", e); renderVol((DEMO.movers?.[curTF] || DEMO.movers?.["1D"])?.movers || [], true); }
  try { await loadIndices(); } catch (e) { console.warn("indices", e); renderIndices((DEMO.indices || []).map((r) => ({ ...r, spark: demoSpark(r.sym) })), true); }
}

function initApp() {
  setupControls();
  setupWatchlistModal();
  setupRunButton();
  refresh().catch((e) => console.warn("refresh failed", e));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
