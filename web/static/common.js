/** Shared theme, i18n, share/download  -  CASSANDRA · netie.ai */
window.CassandraCommon = (function () {
  const STORAGE_THEME = "cassandra-theme";
  const STORAGE_LANG = "cassandra-lang";

  const DASH_I18N = {
    en: {
      tagline: "Daily market desk with traceable editions, timestamps, and score context.",
      nextUpdate: "Next update",
      crsLabel: "Crash Risk Score",
      home: "Home",
      zoneTitle: "Risk zone",
      fragility: "Fragility",
      trigger: "Trigger",
      phase: "Market phase",
      confidence: "Confidence",
      factorsTitle: "What’s driving the score",
      subTitle: "full breakdown for subscribers",
      subBody: "Unlock trigger board, watchlist levels, edition archive retrieval, and API access.",
      donateTitle: "Keep this research free",
      donateBody: "One-off tip  -  thank you for supporting the work.",
      digestTitle: "Get the daily brief",
      digestBody: "Pre-market and during-session editions on trading days.",
      shareTitle: "Open today’s desk edition",
      shareBody: "Read the full narrative, copy a dated link, or print it for archive.",
      shareCopy: "Copy link",
      shareNative: "Share",
      sharePrint: "Print / PDF",
      shareDownload: "Download HTML",
      shareView: "Newspaper",
      referralTitle: "Refer a friend",
      referralBody: "When they subscribe, you get 7 days of API access on the top plan.",
      referralCopy: "Copy referral link",
      insideZone: "In",
      belowMania: "points below Mania",
      coverage: "Data coverage",
      coverageNote: "wider band when sources are thin",
      accessDelayed: "Free plan: scores are 2 days behind. Upgrade for today’s edition.",
      accessLive: "You’re on a live plan  -  today’s score.",
      sessionPreMarket: "Pre-market · NASDAQ",
      sessionDuring: "During session · NASDAQ",
      apiFrom: "Subscriber research desk",
      asof: "as of",
      noData: "No data yet",
      footerLegal: "Research desk for decision support and market monitoring.",
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
      donateBody: "一次性捐赠  -  按地区路由支付方式。",
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
      footerLegal: "个人研究工具  -  非投资建议。",
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
      donateBody: "Sumbangan sekali  -  kaedah bayaran mengikut wilayah.",
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
      footerLegal: "Alat penyelidikan peribadi  -  bukan nasihat kewangan.",
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

  async function shareNative(asof, title, text) {
    const url = reportUrl(asof);
    if (navigator.share) {
      try {
        await navigator.share({ title: title || "Cassandra's Daily", url, text: text || "" });
        return true;
      } catch (e) {
        if (e.name === "AbortError") return false;
      }
    }
    return false;
  }

  async function copyReportLink(asof) {
    await copyText(reportUrl(asof));
    toast("Link copied");
  }

  async function shareReport(asof) {
    const shared = await shareNative(asof, "Cassandra's Daily", "Today's market risk brief from Cassandra.");
    if (!shared) await copyReportLink(asof);
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

  function buildClientDiagnostics() {
    let lang = null;
    try { lang = localStorage.getItem(STORAGE_LANG); } catch (_) { /* ignore */ }
    return {
      app_version: (window.CASSANDRA_CONFIG && window.CASSANDRA_CONFIG.version) || "unknown",
      url: location.href,
      path: location.pathname,
      lang: lang || document.documentElement.lang,
      theme: document.documentElement.getAttribute("data-theme"),
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      client_time: new Date().toISOString(),
      user_agent: navigator.userAgent,
    };
  }

  async function sendContact(message, email) {
    const r = await fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        email: email || undefined,
        client: buildClientDiagnostics(),
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Contact failed");
    return d;
  }

  function openContactFlow() {
    const msg = window.prompt("Message for the Cassandra research desk:");
    if (!msg || !msg.trim()) return;
    const email = window.prompt("Your email (optional, for reply):") || "";
    sendContact(msg.trim(), email.trim())
      .then((d) => toast(d.email_sent ? "Message sent  -  we'll reply soon." : "Message logged  -  email pending config."))
      .catch(() => toast("Could not send contact. Try desk@netie.ai"));
  }

  function referralUrl() {
    return `${location.origin}/subscribe?ref=${referralCode()}`;
  }

  const SESSION_KEY = "cassandra-session";
  const JWT_KEY = "cassandra_jwt";

  function getJwt() {
    try {
      return sessionStorage.getItem(JWT_KEY) || "";
    } catch (_) {
      return "";
    }
  }

  function authHeaders(extra) {
    const h = Object.assign({}, extra || {});
    const jwt = getJwt();
    if (jwt) h.Authorization = "Bearer " + jwt;
    return h;
  }

  function clearAuth() {
    try {
      sessionStorage.removeItem(JWT_KEY);
    } catch (_) { /* ignore */ }
    setSession(null);
  }

  function bootstrapAuth() {
    const jwt = getJwt();
    if (!jwt) return Promise.resolve(null);
    return fetch("/api/auth/me", { headers: authHeaders() })
      .then(function (r) {
        if (!r.ok) {
          clearAuth();
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.email) return null;
        const name = data.display_name || data.email.split("@")[0];
        setSession({
          name: name,
          email: data.email,
          tier: data.tier_label || data.tier || "Free",
          tierId: data.tier || "free",
          initials: name.slice(0, 2).toUpperCase(),
        });
        return data;
      })
      .catch(function () {
        return null;
      });
  }

  function getSession() {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function setSession(user) {
    try {
      if (user) localStorage.setItem(SESSION_KEY, JSON.stringify(user));
      else localStorage.removeItem(SESSION_KEY);
    } catch (_) { /* ignore */ }
    renderAccountMenu();
  }

  function signOut() {
    fetch("/api/auth/logout", { method: "POST" }).catch(function () { /* ignore */ });
    clearAuth();
    toast("Signed out");
  }

  const LANG_ORDER = ["en", "zh", "ms"];
  const LANG_LABELS = { en: "EN", zh: "文", ms: "MS" };

  function initLangCycle(onChange) {
    const btn = document.getElementById("lang-cycle-btn");
    const lbl = document.getElementById("lang-cycle-lbl");
    if (!btn || !lbl) return detectLang();

    let lang = detectLang();
    if (!DASH_I18N[lang]) lang = "en";

    const sync = () => {
      lbl.textContent = LANG_LABELS[lang] || "EN";
      document.documentElement.lang = lang === "zh" ? "zh-CN" : lang;
      setLang(lang);
      if (onChange) onChange(lang);
    };

    sync();
    btn.addEventListener("click", () => {
      const idx = LANG_ORDER.indexOf(lang);
      lang = LANG_ORDER[(idx + 1) % LANG_ORDER.length];
      try { localStorage.setItem(STORAGE_LANG, lang); } catch (_) { /* ignore */ }
      sync();
    });
    return lang;
  }

  function initAccountMenu() {
    const btn = document.getElementById("acct-btn");
    const menu = document.getElementById("acct-menu");
    if (!btn || !menu) return;

    bootstrapAuth().finally(function () {
      renderAccountMenu();
    });

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = menu.hidden;
      menu.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".acct-wrap")) {
        menu.hidden = true;
        btn.setAttribute("aria-expanded", "false");
      }
    });
  }

  function renderAccountMenu() {
    const menu = document.getElementById("acct-menu");
    const btn = document.getElementById("acct-btn");
    if (!menu || !btn) return;

    const session = getSession();
    const loggedIn = Boolean(session?.name);

    btn.classList.toggle("acct-active", loggedIn);

    if (loggedIn) {
      menu.innerHTML = `
        <button type="button" class="acct-item" data-acct-action="agents"><i class="ti ti-cpu" aria-hidden="true"></i>My agents</button>
        <button type="button" class="acct-item" data-acct-action="watchlist"><i class="ti ti-star" aria-hidden="true"></i>My watchlist</button>
        <button type="button" class="acct-item" data-acct-action="settings"><i class="ti ti-settings" aria-hidden="true"></i>Settings</button>
        <button type="button" class="acct-item" data-acct-action="contact"><i class="ti ti-message-2" aria-hidden="true"></i>Contact</button>
        <button type="button" class="acct-item acct-item-last" data-acct-action="signout"><i class="ti ti-logout" aria-hidden="true"></i>Sign out</button>
        <div class="acct-footer">
          <div class="acct-avatar">${(session.initials || session.name.slice(0, 2)).toUpperCase()}</div>
          <div class="acct-user-meta">
            <div class="acct-user-name">${session.name}</div>
            <div class="acct-user-tier">${session.tier || "Pro Desk · $9.99"}</div>
          </div>
        </div>`;
    } else {
      menu.innerHTML = `
        <button type="button" class="acct-item" data-acct-action="signin"><i class="ti ti-login" aria-hidden="true"></i>Sign in</button>
        <button type="button" class="acct-item" data-acct-action="signup"><i class="ti ti-user-plus" aria-hidden="true"></i>Create account</button>
        <button type="button" class="acct-item acct-item-last" data-acct-action="contact"><i class="ti ti-message-2" aria-hidden="true"></i>Contact</button>`;
    }

    menu.querySelectorAll("[data-acct-action]").forEach((el) => {
      el.addEventListener("click", () => {
        const action = el.getAttribute("data-acct-action");
        menu.hidden = true;
        btn.setAttribute("aria-expanded", "false");
        if (action === "signin") window.location.href = "/login.html";
        else if (action === "signup") window.location.href = "/signup.html";
        else if (action === "contact") openContactFlow();
        else if (action === "agents") window.location.href = "/stocks/NOW";
        else if (action === "watchlist") window.location.href = "/#watchlist";
        else if (action === "settings") window.location.href = "/subscribe?settings=1";
        else if (action === "signout") signOut();
      });
    });
  }

  function updateThemeIcon() {
    const icon = document.querySelector("#theme-toggle i");
    if (!icon) return;
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    icon.className = dark ? "ti ti-sun" : "ti ti-moon";
  }

  function paymentMethodHtml() {
    const tz = (Intl.DateTimeFormat().resolvedOptions().timeZone || "");
    if (/Kuala_Lumpur|Singapore|Bangkok/.test(tz)) {
      return '<div class="pay-note">FPX · TnG · DuitNow (MYR) · via Billplz</div>';
    }
    if (/Shanghai|Chongqing|Harbin/.test(tz)) {
      return '<div class="pay-note">支付宝 · 微信支付 via Airwallex</div>';
    }
    return '<div class="pay-note">Stripe · PayPal · cancel anytime</div>';
  }

  function initThemeToggle(defaultDark) {
    initTheme(defaultDark);
    updateThemeIcon();
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
      toggleTheme();
      updateThemeIcon();
    });
  }

  return {
    DASH_I18N,
    detectLang,
    setLang,
    initTheme,
    toggleTheme,
    reportUrl,
    shareReport,
    shareNative,
    copyReportLink,
    downloadHtml,
    copyText,
    toast,
    referralCode,
    referralUrl,
    getSession,
    setSession,
    signOut,
    authHeaders,
    getJwt,
    bootstrapAuth,
    clearAuth,
    initAccountMenu,
    initLangCycle,
    initThemeToggle,
    updateThemeIcon,
    paymentMethodHtml,
    buildClientDiagnostics,
    sendContact,
    openContactFlow,
  };
})();
