/** Analog resolution tier demo  -  illustrative until archives wired. */
const ANALOG_UI = {
  en: {
    section: "Analog resolution",
    headline: "The market has been here before. Here's what happened next.",
    sub: "Illustrative demo until archives are wired. Each outcome links to a source.",
    footnote: "History is an analog, not a forecast. Past outcomes do not predict future results.",
    similarity: "similarity",
    nextDay: "Next day",
    nextWeek: "Next week",
    nextMonth: "Next month",
    tabRep: "Report · $4.99",
    tabPro: "Pro · $9.99",
    tabApi: "API · $49.99",
  },
  zh: {
    section: "历史类比解析",
    headline: "市场曾经到过这里。接下来发生了什么？",
    sub: "演示数据，待历史档案接入后替换。每个结果均链接至来源。",
    footnote: "历史是类比，不是预测。过往结果不代表未来表现。",
    similarity: "相似度",
    nextDay: "次日",
    nextWeek: "次周",
    nextMonth: "次月",
    tabRep: "报告版 · $4.99",
    tabPro: "专业版 · $9.99",
    tabApi: "API · $49.99",
  },
  ms: {
    section: "Penyelesaian analog",
    headline: "Pasaran pernah berada di sini. Apa yang berlaku seterusnya?",
    sub: "Demo ilustratif sehingga arkib disambungkan. Setiap hasil dipautkan ke sumber.",
    footnote: "Sejarah ialah analog, bukan ramalan. Hasil lalu tidak meramalkan hasil masa depan.",
    similarity: "persamaan",
    nextDay: "Hari seterusnya",
    nextWeek: "Minggu seterusnya",
    nextMonth: "Bulan seterusnya",
    tabRep: "Laporan · $4.99",
    tabPro: "Pro · $9.99",
    tabApi: "API · $49.99",
  },
};

const ANALOG_TIERS = {
  en: {
    rep: {
      cap: "Report tier shows the single closest analog and its next-day resolution for the broad market. One era, one outcome.",
      items: [
        {
          era: "Mar 2000 · Dot-com peak",
          sim: "0.81",
          headline: '"Tech demand seen insatiable", capex guidance raised across sector',
          res: [{ w: "Next day", mkt: "NASDAQ", v: "+1.9%", c: "#15803D" }],
          src: "WSJ archive · Mar 13 2000",
        },
      ],
    },
    pro: {
      cap: "Pro tier resolves the next day, next week, and next month for the broad market, across three analogs from different eras.",
      items: [
        {
          era: "Mar 2000 · Dot-com peak",
          sim: "0.81",
          headline: "Capex guidance raised across tech; euphoric coverage",
          res: [
            { w: "Next day", mkt: "NASDAQ", v: "+1.9%", c: "#15803D" },
            { w: "Next week", mkt: "NASDAQ", v: "-4.2%", c: "#B91C1C" },
            { w: "Next month", mkt: "NASDAQ", v: "-14.8%", c: "#7F1D1D" },
          ],
          src: "WSJ · Mar 2000",
        },
        {
          era: "Oct 2007 · Pre-GFC top",
          sim: "0.74",
          headline: 'Financials reassure on subprime exposure; "contained"',
          res: [
            { w: "Next day", mkt: "S&P 500", v: "+0.4%", c: "#15803D" },
            { w: "Next week", mkt: "S&P 500", v: "-1.1%", c: "#B91C1C" },
            { w: "Next month", mkt: "S&P 500", v: "-4.4%", c: "#B91C1C" },
          ],
          src: "Reuters · Oct 2007",
        },
        {
          era: "Nov 2021 · Everything bubble",
          sim: "0.69",
          headline: 'Growth multiples justified by "new paradigm" narratives',
          res: [
            { w: "Next day", mkt: "S&P 500", v: "-0.3%", c: "#B91C1C" },
            { w: "Next week", mkt: "S&P 500", v: "-2.2%", c: "#B91C1C" },
            { w: "Next month", mkt: "S&P 500", v: "-3.5%", c: "#B91C1C" },
          ],
          src: "Bloomberg · Nov 2021",
        },
      ],
    },
    api: {
      cap: "API tier spans 1990–2026: up to five analogs and a daily single-stock resolution. Pick one ticker per day to project against its closest historical matches.",
      items: [
        {
          era: "Mar 2000 · Dot-com peak",
          sim: "0.81",
          headline: 'Cisco-led capex euphoria; "insatiable" demand',
          res: [
            { w: "Next day", mkt: "MU", v: "+2.4%", c: "#15803D" },
            { w: "Next week", mkt: "MU", v: "-6.1%", c: "#B91C1C" },
            { w: "Next month", mkt: "MU", v: "-22.3%", c: "#7F1D1D" },
          ],
          src: "WSJ · Mar 2000",
        },
        {
          era: "Jul 2018 · Memory cycle top",
          sim: "0.77",
          headline: 'DRAM pricing "structurally higher"; glut fears dismissed',
          res: [
            { w: "Next day", mkt: "MU", v: "-1.2%", c: "#B91C1C" },
            { w: "Next week", mkt: "MU", v: "-3.8%", c: "#B91C1C" },
            { w: "Next month", mkt: "MU", v: "-19.4%", c: "#7F1D1D" },
          ],
          src: "Barron's · Jul 2018",
        },
        {
          era: "Oct 2007 · Pre-GFC",
          sim: "0.71",
          headline: 'Semis "decoupled" from credit stress',
          res: [
            { w: "Next day", mkt: "MU", v: "+0.8%", c: "#15803D" },
            { w: "Next week", mkt: "MU", v: "-2.9%", c: "#B91C1C" },
            { w: "Next month", mkt: "MU", v: "-11.2%", c: "#B91C1C" },
          ],
          src: "Reuters · Oct 2007",
        },
        {
          era: "Jan 2022 · Rate shock",
          sim: "0.68",
          headline: 'Chip shortage "permanent"; pricing power overstated',
          res: [
            { w: "Next day", mkt: "MU", v: "-2.1%", c: "#B91C1C" },
            { w: "Next week", mkt: "MU", v: "-5.4%", c: "#B91C1C" },
            { w: "Next month", mkt: "MU", v: "-13.7%", c: "#B91C1C" },
          ],
          src: "Bloomberg · Jan 2022",
        },
        {
          era: "Sep 1995 · Early tech run",
          sim: "0.61",
          headline: 'PC demand "endless"; memory makers expand capacity',
          res: [
            { w: "Next day", mkt: "MU", v: "+3.1%", c: "#15803D" },
            { w: "Next week", mkt: "MU", v: "+1.2%", c: "#15803D" },
            { w: "Next month", mkt: "MU", v: "-8.9%", c: "#B91C1C" },
          ],
          src: "NYT archive · Sep 1995",
        },
      ],
    },
  },
  zh: {
    rep: {
      cap: "报告版展示最接近的单一历史类比及其次日大盘结果。一个时代，一个结果。",
      items: [{
        era: "2000 年 3 月 · 互联网泡沫峰值",
        sim: "0.81",
        headline: "「科技需求看似无穷无尽」，全行业上调资本支出指引",
        res: [{ w: "次日", mkt: "NASDAQ", v: "+1.9%", c: "#15803D" }],
        src: "WSJ 档案 · 2000 年 3 月 13 日",
      }],
    },
    pro: { cap: "专业版对大盘给出次日、次周、次月结果，覆盖三个不同时代的历史类比。", items: [] },
    api: { cap: "API 版覆盖 1990–2026：最多五个类比，以及每日单股解析。每天选一个代码，对照其最接近的历史匹配。", items: [] },
  },
  ms: {
    rep: {
      cap: "Peringkat Laporan menunjukkan analog terdekat tunggal dan penyelesaian hari seterusnya untuk pasaran luas. Satu era, satu hasil.",
      items: [{
        era: "Mac 2000 · Puncak dot-com",
        sim: "0.81",
        headline: '"Permintaan teknologi kelihatan tidak pernah puas", panduan capex dinaikkan merentasi sektor',
        res: [{ w: "Hari seterusnya", mkt: "NASDAQ", v: "+1.9%", c: "#15803D" }],
        src: "Arkib WSJ · 13 Mac 2000",
      }],
    },
    pro: { cap: "Peringkat Pro menyelesaikan hari seterusnya, minggu seterusnya, dan bulan seterusnya untuk pasaran luas, merentasi tiga analog dari era berbeza.", items: [] },
    api: { cap: "Peringkat API merangkumi 1990–2026: sehingga lima analog dan penyelesaian saham tunggal harian.", items: [] },
  },
};

// Fill zh/ms pro+api from EN structure with translated window labels
["pro", "api"].forEach((tier) => {
  ["zh", "ms"].forEach((lang) => {
    ANALOG_TIERS[lang][tier].items = ANALOG_TIERS.en[tier].items.map((it, i) => {
      const ui = ANALOG_UI[lang];
      const wMap = { "Next day": ui.nextDay, "Next week": ui.nextWeek, "Next month": ui.nextMonth };
      return {
        ...it,
        res: it.res.map((r) => ({ ...r, w: wMap[r.w] || r.w })),
        ...(lang === "zh" && tier === "pro" && i === 0 ? { era: "2000 年 3 月 · 互联网泡沫峰值", headline: "科技行业上调资本支出指引；报道情绪亢奋" } : {}),
        ...(lang === "ms" && tier === "pro" && i === 0 ? { era: "Mac 2000 · Puncak dot-com", headline: "Panduan capex dinaikkan merentasi teknologi; liputan euforia" } : {}),
      };
    });
  });
});

let analogLang = "en";
let analogTierKey = "rep";

function resLabel(w, lang) {
  const ui = ANALOG_UI[lang] || ANALOG_UI.en;
  if (w === "Next day" || w === ui.nextDay || w === "次日" || w === "Hari seterusnya") return ui.nextDay;
  if (w === "Next week" || w === ui.nextWeek || w === "次周" || w === "Minggu seterusnya") return ui.nextWeek;
  if (w === "Next month" || w === ui.nextMonth || w === "次月" || w === "Bulan seterusnya") return ui.nextMonth;
  return w;
}

function renderAnalogCard(it, lang) {
  const ui = ANALOG_UI[lang] || ANALOG_UI.en;
  const resHtml = it.res.map((r) => `
    <div class="analog-res-cell">
      <div class="analog-res-label">${resLabel(r.w, lang)}</div>
      <div class="cm analog-res-val" style="color:${r.c}">${r.v}</div>
      <div class="analog-res-mkt">${r.mkt}</div>
    </div>`).join("");
  return `<div class="analog-card">
    <div class="analog-card-head">
      <span class="cp analog-era">${it.era}</span>
      <span><span style="font-size:8px;text-transform:uppercase;letter-spacing:0.06em;color:var(--color-text-tertiary);">${ui.similarity} </span><span class="cm analog-sim">${it.sim}</span></span>
    </div>
    <div class="analog-headline-text">${it.headline}</div>
    <div class="analog-res-grid">${resHtml}</div>
    <div class="analog-src"><i class="ti ti-external-link" aria-hidden="true"></i><span>${it.src}</span></div>
  </div>`;
}

function applyAnalogChrome(lang) {
  const ui = ANALOG_UI[lang] || ANALOG_UI.en;
  const set = (id, text) => { const el = document.getElementById(id); if (el && text) el.textContent = text; };
  set("analog-section-label", ui.section);
  set("analog-h2", ui.headline);
  set("analog-sub", ui.sub);
  set("analog-footnote", ui.footnote);
  set("analog-tab-rep", ui.tabRep);
  set("analog-tab-pro", ui.tabPro);
  set("analog-tab-api", ui.tabApi);
}

function setAnalogTier(key) {
  analogTierKey = key;
  ["rep", "pro", "api"].forEach((k) => {
    document.getElementById(`analog-tab-${k}`)?.classList.toggle("on", k === key);
  });
  const tiers = ANALOG_TIERS[analogLang] || ANALOG_TIERS.en;
  const t = tiers[key] || ANALOG_TIERS.en[key];
  const cap = document.getElementById("analog-cap");
  const list = document.getElementById("analog-list");
  if (cap) cap.textContent = t.cap;
  if (list) list.innerHTML = t.items.map((it) => renderAnalogCard(it, analogLang)).join("");
}

function setAnalogLang(lang) {
  if (!ANALOG_UI[lang]) lang = "en";
  analogLang = lang;
  applyAnalogChrome(lang);
  setAnalogTier(analogTierKey);
}

function initAnalogResolution() {
  if (!document.getElementById("analog-list")) return;
  ["rep", "pro", "api"].forEach((k) => {
    document.getElementById(`analog-tab-${k}`)?.addEventListener("click", () => setAnalogTier(k));
  });
  const saved = (() => { try { return localStorage.getItem("cassandra-lang"); } catch (_) { return null; } })();
  setAnalogLang(saved === "zh" || saved === "ms" ? saved : "en");
}

window.setAnalogLang = setAnalogLang;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAnalogResolution);
} else {
  initAnalogResolution();
}
