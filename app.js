/** CASSANDRA home dashboard v3  -  watchlist, score inputs, volatility, fear/greed */

const BCOLORS = ["#15803D", "#4D7C0F", "#92400E", "#C2410C", "#B91C1C", "#7F1D1D"];
const BTHRESH = [0, 20, 35, 50, 65, 80, 100];
const UP = "#15803D";
const DOWN = "#B91C1C";
const TF_FRAMES = ["1D", "5D", "1M"];
const WL_STORAGE = "cassandra-watchlist";
const WL_USER_KEY = "cassandra-user-id";

const DEMO = window.CassandraDemo || {};

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
    ed: "Late City Edition", cov: "Live coverage: 100%", analog: "Today feels like March 14, 2000",
    desk: "Global Market Desk", hwl: "Watchlist", editwl: "Edit", hsi: "Score Inputs",
    read: "Read today's full edition →", edbtn: "Morning edition", hvol: "Top Volatility",
    hfg: "Fear & Greed", hidx: "Index Snapshot", fcHead: "Platform",
    fpub: "Cassandra Research Desk · crash.netie.ai", fdisc: "For decision support only. Not financial advice.",
    wlTitle: "Edit watchlist", wlHint: "Pick tickers below or search to add.",
    siTrigger: "Trigger", siFrag: "Fragility", siCapex: "Capex NLP",
    fgFear: "Fear", fgGreed: "Greed", fgNeutral: "Neutral",
    phaseDist: "distribution range",
    bands: ["Stable", "Complacent", "Aware", "Mania", "Danger", "Crisis"],
    lvlHigh: "high", lvlElevated: "elevated", lvlModerate: "moderate", lvlCut: "cut signal", lvlNoCut: "no cut yet",
    p1: "Crash risk reflects a market that has not yet broken distribution but lacks the catalyst to recover toward neutral territory.",
    p2: "The primary variable this cycle is hyperscaler capital expenditure intent, still unresolved across major cloud vendors.",
  },
  zh: {
    ed: "晚城版", cov: "实时覆盖率：100%", analog: "今日情势令人想起 2000 年 3 月 14 日",
    desk: "全球市场观察台", hwl: "自选股", editwl: "编辑", hsi: "评分输入",
    read: "阅读今日完整版 →", edbtn: "早版", hvol: "高波动排行",
    hfg: "恐慌贪婪指数", hidx: "指数速览", fcHead: "平台功能",
    fpub: "Cassandra 研究台 · crash.netie.ai", fdisc: "仅供决策支持，非投资建议。",
    wlTitle: "编辑自选股", wlHint: "点击下方代码或搜索添加。",
    siTrigger: "触发器", siFrag: "脆弱性", siCapex: "资本支出 NLP",
    fgFear: "恐慌", fgGreed: "贪婪", fgNeutral: "中性",
    phaseDist: "派发区间",
    bands: ["稳定", "自满", "预警", "狂热", "危险", "危机"],
    lvlHigh: "偏高", lvlElevated: "抬升", lvlModerate: "中等", lvlCut: "削减信号", lvlNoCut: "尚无削减",
    p1: "崩溃风险反映市场尚未打破分布结构，但缺乏向中性区间修复的催化剂。",
    p2: "本轮核心变量是超大规模云厂商的资本开支意向，仍未在各主要云厂商间形成一致结论。",
  },
  ms: {
    ed: "Edisi Kota Lewat", cov: "Liputan langsung: 100%", analog: "Hari ini terasa seperti 14 Mac 2000",
    desk: "Meja Pasaran Global", hwl: "Senarai Pantau", editwl: "Edit", hsi: "Input Skor",
    read: "Baca edisi penuh hari ini →", edbtn: "Edisi pagi", hvol: "Volatiliti Tertinggi",
    hfg: "Takut & Tamak", hidx: "Gambaran Indeks", fcHead: "Platform",
    fpub: "Meja Penyelidikan Cassandra · crash.netie.ai", fdisc: "Sokongan keputusan sahaja. Bukan nasihat kewangan.",
    wlTitle: "Edit senarai pantau", wlHint: "Pilih ticker di bawah atau cari untuk tambah.",
    siTrigger: "Pencetus", siFrag: "Kerapuhan", siCapex: "NLP Capex",
    fgFear: "Takut", fgGreed: "Tamak", fgNeutral: "Neutral",
    phaseDist: "julat pengedaran",
    bands: ["Stabil", "Puas Diri", "Sedar", "Mania", "Bahaya", "Krisis"],
    lvlHigh: "tinggi", lvlElevated: "meningkat", lvlModerate: "sederhana", lvlCut: "isyarat potong", lvlNoCut: "belum potong",
    p1: "Risiko runtuh mencerminkan pasaran yang belum memecah taburan tetapi kekurangan pemangkin untuk pulih ke zon neutral.",
    p2: "Pemboleh ubah utama kitaran ini ialah niat perbelanjaan modal hyperscaler, masih belum selesai merentasi vendor awan utama.",
  },
};

const CC = window.CassandraCommon || {};
let currentLang = "en";
let curTF = "1D";
let volScale = 14;
let lastAsof = null;

function tx(key) {
  return T[currentLang]?.[key] ?? T.en[key] ?? key;
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

function bandColor(crs) {
  return BCOLORS[bandIndex(crs)];
}

function renderScale(crs, bands) {
  const idx = bandIndex(crs);
  return `<div class="scale-labels">${bands.map((b, i) =>
    `<span style="color:${i === idx ? BCOLORS[i] : "var(--color-text-tertiary)"};font-weight:${i === idx ? "600" : "400"}">${b}${i === idx ? " ◀" : ""}</span>`
  ).join("")}</div>`;
}

function fmtPct(pct) {
  const up = pct >= 0;
  return { up, color: up ? UP : DOWN, text: `${up ? "+" : ""}${Number(pct).toFixed(2)}%` };
}

function spark(d, w, h, c, lbl) {
  if (!d?.length) return "";
  const mn = Math.min(...d);
  const mx = Math.max(...d);
  const rng = mx - mn || 1;
  const pts = d.map((v, i) => `${(i / (d.length - 1)) * w},${h - ((v - mn) / rng) * (h - 2) - 1}`).join(" ");
  return `<svg role="img" aria-label="${lbl}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" class="spark"><polyline points="${pts}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el && text != null) el.textContent = text;
}

function applyLang() {
  const t = T[currentLang];
  const ids = {
    "h-ed": t.ed, "h-cov": t.cov, "analog-t": t.analog, "desk-l": t.desk,
    "h-wl": t.hwl, "edit-wl": t.editwl, "h-si": t.hsi, "read-l": t.read,
    "ed-btn": t.edbtn, "h-vol": t.hvol, "h-fg": t.hfg, "h-idx": t.hidx, "fc-head": t.fcHead,
    "f-pub": t.fpub, "f-disc": t.fdisc, "wl-modal-title": t.wlTitle, "wl-modal-hint": t.wlHint,
  };
  Object.keys(ids).forEach((id) => setText(id, ids[id]));
  setDateLine(lastAsof);
  if (window.__lastScore) renderScoreInputs(window.__lastScore);
  if (window.__lastHi) populateNarrative(window.__lastHi);
  else { setText("bp1", t.p1); setText("bp2", t.p2); }
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const d = await r.json();
    reply.textContent = d.reply || d.response || "No response.";
  } catch (_) {
    reply.textContent = "Agent unavailable offline.";
  }
}

function renderWatchlist(rows) {
  const el = document.getElementById("wl-tbl");
  if (!el) return;
  el.innerHTML = "";
  if (!rows?.length) {
    el.innerHTML = '<div class="home-empty">No tickers.</div>';
    return;
  }
  rows.forEach((r) => {
    try {
      const { color, text } = fmtPct(Number(r.pct) || 0);
      el.innerHTML += `<div class="rb home-pt-row">
        <a href="/stocks/${r.sym}" class="cm home-pt-sym home-ticker-link">${r.sym}</a>
        <span class="cm home-pt-px">${r.px ?? "-"}</span>
        <span class="cm home-pt-pct" style="color:${color}">${text}</span>
      </div>`;
    } catch (_) { /* skip */ }
  });
}

function renderScoreInputs(score) {
  const el = document.getElementById("si-rows");
  if (!el || !score) return;
  const capex = score.capex_cut_nlp ?? score.extra?.capex_cut_nlp;
  const rows = [
    { n: tx("siTrigger"), v: score.trigger?.toFixed(2) ?? "-", lbl: labelLevel(score.trigger) },
    { n: tx("siFrag"), v: score.fragility?.toFixed(2) ?? "-", lbl: labelLevel(score.fragility) },
    { n: tx("siCapex"), v: capex != null ? Number(capex).toFixed(2) : "-", lbl: capex != null && Number(capex) > 0.5 ? tx("lvlCut") : tx("lvlNoCut") },
  ];
  el.innerHTML = rows.map((r) => `<div class="rb home-si-row">
    <span class="home-si-name">${r.n}</span>
    <span class="cm home-si-val">${r.v}</span>
    <span class="home-si-lbl">${r.lbl}</span>
  </div>`).join("");
}

function labelLevel(v) {
  if (v == null) return "-";
  const n = Number(v);
  if (n >= 0.65) return tx("lvlHigh");
  if (n >= 0.45) return tx("lvlElevated");
  return tx("lvlModerate");
}

function fgLabelText(label) {
  const l = String(label || "").toLowerCase();
  if (l.includes("fear")) return tx("fgFear");
  if (l.includes("greed")) return tx("fgGreed");
  return tx("fgNeutral");
}

function renderVol(movers) {
  const vr = document.getElementById("vol-rows");
  if (!vr) return;
  vr.innerHTML = "";
  (movers || []).forEach((r) => {
    try {
      const { color, text } = fmtPct(Number(r.pct) || 0);
      const bw = Math.min(100, Math.abs(Number(r.pct) || 0) / volScale * 100).toFixed(1);
      vr.innerHTML += `<div class="home-mov-row">
        <span class="cm home-mov-sym">${r.sym}</span>
        <div class="home-mov-bar"><div style="width:${bw}%;background:${color}"></div></div>
        <span class="cm home-mov-pct" style="color:${color}">${text.replace(".00", ".0")}</span>
      </div>`;
    } catch (_) { /* skip */ }
  });
}

function renderIndices(indices) {
  const ie = document.getElementById("idx-el");
  if (!ie) return;
  ie.innerHTML = "";
  (indices || []).forEach((r) => {
    try {
      const { color, text } = fmtPct(Number(r.pct) || 0);
      ie.innerHTML += `<div class="home-idx-row">
        <span class="cm home-idx-sym">${r.sym}</span>
        <span class="cm home-idx-val">${r.val ?? "-"}</span>
        ${spark(r.spark || r.d, 42, 15, color, r.sym)}
        <span class="cm home-idx-pct" style="color:${color}">${text}</span>
      </div>`;
    } catch (_) { /* skip */ }
  });
}

function renderFearGreed(fg) {
  if (!fg) return;
  const val = document.getElementById("fg-val");
  const lbl = document.getElementById("fg-label");
  const sp = document.getElementById("fg-spark");
  if (val) {
    val.textContent = fg.value;
    val.style.color = fg.color || DOWN;
  }
  if (lbl) {
    lbl.textContent = fgLabelText(fg.label);
    lbl.style.color = fg.color || DOWN;
  }
  if (sp) sp.innerHTML = spark(fg.spark || [], 62, 18, fg.color || DOWN, "Fear greed");
}

function phaseColor(raw) {
  const p = String(raw || "").toLowerCase();
  if (p.includes("distribution") || p.includes("markdown") || p.includes("climax")) return "var(--color-danger)";
  if (p.includes("aware") || p.includes("upthrust") || p.includes("undetermined")) return "var(--color-warn)";
  if (p.includes("accumulation") || p.includes("secondary")) return "var(--color-neutral)";
  if (p.includes("markup")) return "var(--color-ok)";
  return "var(--color-warn)";
}

function phaseEmoji(raw) {
  const p = String(raw || "").toLowerCase();
  if (p.includes("distribution") || p.includes("markdown") || p.includes("climax")) return "📉";
  if (p.includes("markup")) return "📈";
  if (p.includes("accumulation") || p.includes("secondary")) return "🔄";
  return "⚠️";
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
  const raw = score.phase;
  const label = String(raw).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  labelEl.textContent = `${phaseEmoji(raw)} ${label}`;
  labelEl.style.color = phaseColor(raw);
  const conf = score.phase_confidence;
  confEl.textContent = conf != null ? `(${Math.round(conf * 100)}% conf)` : "";
}

function populateScore(score) {
  if (!score) {
    setText("crs", "-");
    renderPhase(null);
    return;
  }
  lastAsof = score.asof;
  setText("crs", Number(score.crs).toFixed(1));
  renderPhase(score);
  const band = score.band || T.en.bands[bandIndex(score.crs)];
  setText("bname", band.toUpperCase());
  const bEl = document.getElementById("bname");
  if (bEl) bEl.style.color = bandColor(score.crs);
  const hw = score.band_halfwidth != null ? score.band_halfwidth : 1;
  setText("band-range", `${(score.crs - hw).toFixed(1)} – ${(score.crs + hw).toFixed(1)}`);
  const scale = document.getElementById("bscale");
  if (scale) scale.innerHTML = renderScale(score.crs, T[currentLang].bands);
  const cov = score.coverage != null ? `${(score.coverage * 100).toFixed(0)}%` : "100%";
  setText("h-cov", tx("cov").replace("100%", cov));
  renderScoreInputs(score);
}

function populateNarrative(hi) {
  window.__lastHi = hi;
  if (!hi) {
    setText("bp1", tx("p1"));
    setText("bp2", tx("p2"));
    setText("analog-t", tx("analog"));
    return;
  }
  if (hi.analog_date) {
    const analog = document.getElementById("analog-t");
    if (analog) {
      const prefix = currentLang === "zh" ? "今日情势令人想起 " : currentLang === "ms" ? "Hari ini terasa seperti " : "Today feels like ";
      analog.textContent = `${prefix}${hi.analog_date}`;
    }
  } else {
    setText("analog-t", tx("analog"));
  }
  if (hi.headline && currentLang === "en") setText("hl", hi.headline);
  else setText("hl", "");
  setText("bp1", tx("p1"));
  setText("bp2", tx("p2"));
}

function setDateLine(asof) {
  const el = document.getElementById("cdate");
  if (!el) return;
  const d = asof ? new Date(asof + "T12:00:00") : new Date();
  const locale = currentLang === "zh" ? "zh-CN" : currentLang === "ms" ? "ms-MY" : "en-US";
  el.textContent = d.toLocaleDateString(locale, {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }).toUpperCase();
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: uid, tickers }),
      });
    } catch (_) { /* offline */ }
  }
  try {
    const r = await fetch(`/api/watchlist?user=${encodeURIComponent(uid)}`);
    if (r.ok) {
      const d = await r.json();
      if (d.rows?.length) {
        renderWatchlist(d.rows);
        try { localStorage.setItem(WL_STORAGE, JSON.stringify(d.tickers)); } catch (_) { /* ignore */ }
        return d.tickers;
      }
    }
  } catch (_) { /* offline */ }
  renderWatchlist(DEMO.watchlist || []);
  return tickers || ["LEU", "NVDA", "MSFT", "AMZN", "TSM"];
}

async function saveWatchlist(tickers) {
  const uid = userId();
  try { localStorage.setItem(WL_STORAGE, JSON.stringify(tickers)); } catch (_) { /* ignore */ }
  try {
    const r = await fetch("/api/watchlist/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: uid, tickers }),
    });
    if (r.ok) {
      const d = await r.json();
      renderWatchlist(d.rows);
    }
  } catch (_) { /* offline */ }
}

async function fetchLatest() {
  try {
    const r = await fetch("/api/latest");
    if (r.ok) return await r.json();
  } catch (_) { /* offline */ }
  return null;
}

async function fetchHighlights() {
  try {
    const r = await fetch("/api/report/highlights");
    if (r.ok) return await r.json();
  } catch (_) { /* offline */ }
  return null;
}

async function fetchMovers() {
  try {
    const r = await fetch(`/api/movers?tf=${curTF}&sector=tech,semis&limit=10`);
    if (r.ok) {
      const d = await r.json();
      if (d.movers?.length) {
        volScale = d.scale || 14;
        return d.movers;
      }
    }
  } catch (_) { /* offline */ }
  const pack = DEMO.movers?.[curTF] || DEMO.movers?.["1D"];
  volScale = pack?.scale || 14;
  return pack?.movers || [];
}

async function loadIndices() {
  try {
    const r = await fetch("/api/indices");
    if (r.ok) {
      const d = await r.json();
      if (d.indices?.length) {
        renderIndices(d.indices);
        return;
      }
    }
  } catch (_) { /* offline */ }
  renderIndices((DEMO.indices || []).map((r) => ({ ...r, spark: demoSpark(r.sym) })));
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
  renderVol(await fetchMovers());
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

async function safeGet(url, fallback) {
  try {
    const r = await fetch(url);
    if (!r.ok) return fallback;
    const ct = r.headers.get("content-type") || "";
    if (!ct.includes("application/json")) return fallback;
    return await r.json();
  } catch (_) {
    return fallback;
  }
}

function isLocalDev() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

function setupControls() {
  if (CC.initThemeToggle) CC.initThemeToggle(false);
  if (CC.initAccountMenu) CC.initAccountMenu();
  if (CC.initLangCycle) {
    CC.initLangCycle((lang) => {
      currentLang = lang;
      if (!T[currentLang]) currentLang = "en";
      applyLang();
      if (window.__lastScore) {
        populateScore(window.__lastScore);
        const scale = document.getElementById("bscale");
        if (scale) scale.innerHTML = renderScale(window.__lastScore.crs, T[currentLang].bands);
      }
    });
  } else {
    currentLang = CC.detectLang ? CC.detectLang() : "en";
    if (!T[currentLang]) currentLang = "en";
    applyLang();
  }
  document.getElementById("tf-btn")?.addEventListener("click", cycleTF);
}

function setupRunButton() {
  const btn = document.getElementById("runBtn");
  if (!btn || !isLocalDev()) return;
  btn.classList.add("visible");
  btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "Running…";
    await fetch("/api/run", { method: "POST" });
    await refresh();
    btn.disabled = false;
    btn.textContent = "Run cycle";
  };
}

async function refresh() {
  const fgFallback = DEMO.fearGreed || null;
  let score = null;
  let hi = null;
  let fg = null;

  try { score = await fetchLatest(); } catch (e) { console.warn("latest", e); }
  try { hi = await fetchHighlights(); } catch (e) { console.warn("highlights", e); }
  try { fg = await safeGet("/api/signals/fear_greed", null); } catch (e) { console.warn("fg", e); }

  window.__lastScore = score;
  setDateLine(score?.asof || hi?.asof);
  populateScore(score);
  populateNarrative(hi);
  renderFearGreed(fg?.value != null ? fg : fgFallback);

  try { await loadWatchlist(); } catch (e) { console.warn("watchlist", e); renderWatchlist(DEMO.watchlist || []); }
  try { await loadMovers(); } catch (e) { console.warn("movers", e); renderVol((DEMO.movers?.[curTF] || DEMO.movers?.["1D"])?.movers || []); }
  try { await loadIndices(); } catch (e) { console.warn("indices", e); renderIndices((DEMO.indices || []).map((r) => ({ ...r, spark: demoSpark(r.sym) }))); }
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
