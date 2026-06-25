/** Shared theme, i18n, share/download — CASSANDRA · netie.ai */
window.CassandraCommon = (function () {
  const STORAGE_THEME = "cassandra-theme";
  const STORAGE_LANG = "cassandra-lang";

  const DASH_I18N = {
    en: {
      tagline: "Crash Risk Score · decision support only · no execution",
      nextUpdate: "Next score update",
      crsLabel: "Crash Risk Score",
      zoneTitle: "Risk zone",
      fragility: "Fragility (F)",
      trigger: "Trigger (T)",
      phase: "Phase",
      confidence: "Confidence",
      factorsTitle: "Factor breakdown · L/V live · S/B/C for subscribers",
      subTitle: "Full factor access",
      subBody: "Unlock S, B, C factors + daily newspaper report.",
      donateTitle: "Support the research",
      donateBody: "One-off contribution — routed to your local payment method.",
      digestTitle: "Daily thesis digest",
      digestBody: "Newspaper-style report emailed 3× on trading days.",
      shareTitle: "Share today's report",
      shareBody: "Copy a link or download the NYT-style edition for subscribers.",
      shareCopy: "Copy link",
      shareDownload: "Download HTML",
      shareView: "Read newspaper",
      referralTitle: "Refer & earn 7 days free API",
      referralBody: "When someone subscribes with your link, activate a 7-day API trial in your account vouchers.",
      referralCopy: "Copy referral link",
      insideZone: "Inside",
      belowMania: "pts below Mania",
      coverage: "Coverage",
      coverageNote: "wider band when data is thin",
      asof: "as of",
      noData: "No data yet",
      footerLegal: "Personal research tooling — not financial advice.",
      footerDisclaimer: "CRS is a composite index with confidence bands. Low coverage widens uncertainty. No crash-date predictions.",
      credit: "Built by",
      pricing: "Pricing",
      stocks: "Stock demos",
    },
    zh: {
      tagline: "崩盘风险评分 · 决策支持 · 不执行交易",
      nextUpdate: "下次更新",
      crsLabel: "崩盘风险评分",
      zoneTitle: "风险区间",
      fragility: "脆弱性 (F)",
      trigger: "触发器 (T)",
      phase: "阶段",
      confidence: "置信度",
      factorsTitle: "因子分解 · L/V 公开 · S/B/C 订阅解锁",
      subTitle: "完整因子访问",
      subBody: "解锁 S/B/C 因子 + 每日报纸版报告。",
      donateTitle: "支持研究",
      donateBody: "一次性捐赠 — 按地区路由支付方式。",
      digestTitle: "每日论文摘要",
      digestBody: "交易日 3 次发送报纸风格报告。",
      shareTitle: "分享今日报告",
      shareBody: "复制链接或下载 NYT 风格版本。",
      shareCopy: "复制链接",
      shareDownload: "下载 HTML",
      shareView: "阅读报纸版",
      referralTitle: "推荐获 7 天免费 API",
      referralBody: "有人通过您的链接订阅后，可在账户优惠券中激活 7 天 API 试用。",
      referralCopy: "复制推荐链接",
      insideZone: "处于",
      belowMania: "分低于 Mania",
      coverage: "覆盖率",
      coverageNote: "数据不足时带宽加宽",
      asof: "截至",
      noData: "暂无数据",
      footerLegal: "个人研究工具 — 非投资建议。",
      footerDisclaimer: "CRS 为综合指数。低覆盖率扩大不确定性。不预测崩盘日期。",
      credit: "出品",
      pricing: "定价",
      stocks: "股票演示",
    },
    ms: {
      tagline: "Skor Risiko Ranap · sokongan keputusan · tiada pelaksanaan",
      nextUpdate: "Kemas kini seterusnya",
      crsLabel: "Skor Risiko Ranap",
      zoneTitle: "Zon risiko",
      fragility: "Kerapuhan (F)",
      trigger: "Pencetus (T)",
      phase: "Fasa",
      confidence: "Keyakinan",
      factorsTitle: "Pecahan faktor · L/V percuma · S/B/C pelanggan",
      subTitle: "Akses faktor penuh",
      subBody: "Buka kunci S, B, C + laporan harian gaya akhbar.",
      donateTitle: "Sokong penyelidikan",
      donateBody: "Sumbangan sekali — kaedah bayaran mengikut wilayah.",
      digestTitle: "Ringkasan tesis harian",
      digestBody: "Laporan gaya akhbar 3× pada hari dagangan.",
      shareTitle: "Kongsi laporan hari ini",
      shareBody: "Salin pautan atau muat turun edisi gaya NYT.",
      shareCopy: "Salin pautan",
      shareDownload: "Muat turun HTML",
      shareView: "Baca akhbar",
      referralTitle: "Rujuk & dapat 7 hari API percuma",
      referralBody: "Apabila seseorang langgan melalui pautan anda, aktifkan percubaan API 7 hari dalam baucar akaun.",
      referralCopy: "Salin pautan rujukan",
      insideZone: "Dalam zon",
      belowMania: "mata di bawah Mania",
      coverage: "Liputan",
      coverageNote: "jalur lebih lebar apabila data nipis",
      asof: "setakat",
      noData: "Tiada data",
      footerLegal: "Alat penyelidikan peribadi — bukan nasihat kewangan.",
      footerDisclaimer: "CRS ialah indeks komposit. Liputan rendah meluaskan ketidakpastian. Tiada ramalan tarikh ranap.",
      credit: "Dibina oleh",
      pricing: "Harga",
      stocks: "Demo saham",
    },
  };

  function detectLang() {
    try {
      const saved = localStorage.getItem(STORAGE_LANG);
      if (saved && DASH_I18N[saved]) return saved;
    } catch (_) { /* ignore */ }
    const l = navigator.language || "en";
    if (l.startsWith("zh")) return "zh";
    if (l.startsWith("ms") || l === "id") return "ms";
    return "en";
  }

  function setLang(lang) {
    if (!DASH_I18N[lang]) lang = "en";
    try { localStorage.setItem(STORAGE_LANG, lang); } catch (_) { /* ignore */ }
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const t = DASH_I18N[lang][key];
      if (t) el.textContent = t;
    });
    document.querySelectorAll(".lang-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.lang === lang);
    });
    document.documentElement.lang = lang === "zh" ? "zh-CN" : lang;
    return lang;
  }

  function initTheme(defaultDark) {
    let saved = null;
    try { saved = localStorage.getItem(STORAGE_THEME); } catch (_) { /* ignore */ }
    const sys = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = saved || (defaultDark ? "dark" : sys);
    document.documentElement.setAttribute("data-theme", theme);
    return theme;
  }

  function toggleTheme() {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem(STORAGE_THEME, next); } catch (_) { /* ignore */ }
    return next;
  }

  function reportUrl(asof) {
    const base = `${location.origin}/newspaper-report`;
    return asof ? `${base}?asof=${encodeURIComponent(asof)}` : base;
  }

  async function copyText(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return true;
  }

  function toast(msg) {
    let el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2500);
  }

  async function shareReport(asof) {
    const url = reportUrl(asof);
    if (navigator.share) {
      try {
        await navigator.share({ title: "CASSANDRA Report", url, text: "AI sector fragility monitor" });
        return;
      } catch (_) { /* fall through */ }
    }
    await copyText(url);
    toast("Link copied");
  }

  function downloadHtml(filename) {
    const clone = document.documentElement.cloneNode(true);
    clone.querySelectorAll("script").forEach((s) => s.remove());
    const html = "<!DOCTYPE html>\n" + clone.outerHTML;
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function referralCode() {
    let code = null;
    try { code = localStorage.getItem("cassandra-ref"); } catch (_) { /* ignore */ }
    if (!code) {
      code = "NETIE-" + Math.random().toString(36).slice(2, 8).toUpperCase();
      try { localStorage.setItem("cassandra-ref", code); } catch (_) { /* ignore */ }
    }
    return code;
  }

  function referralUrl() {
    return `${location.origin}/subscribe?ref=${referralCode()}`;
  }

  return {
    DASH_I18N,
    detectLang,
    setLang,
    initTheme,
    toggleTheme,
    reportUrl,
    shareReport,
    downloadHtml,
    copyText,
    toast,
    referralCode,
    referralUrl,
  };
})();
