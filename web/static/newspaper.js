/** Cassandra's Daily: dated editions, score, and highlights */
(function () {
  const CC = window.CassandraCommon;
  let selectedAsof = new URLSearchParams(window.location.search).get("asof") || null;
  let editions = [];

  function apiUrl(path) {
    if (!selectedAsof) return path;
    const sep = path.includes("?") ? "&" : "?";
    return `${path}${sep}asof=${encodeURIComponent(selectedAsof)}`;
  }

  function setQueryAsof(asof) {
    const url = new URL(window.location.href);
    if (asof) url.searchParams.set("asof", asof);
    else url.searchParams.delete("asof");
    window.history.replaceState({}, "", url.toString());
  }

  function loadEditionSelector() {
    const sel = document.getElementById("edition-select");
    if (!sel || !editions.length) return;
    sel.innerHTML = editions.map((e) => `<option value="${e.asof}">${e.asof}</option>`).join("");
    const current = selectedAsof || editions[0].asof;
    sel.value = editions.some((e) => e.asof === current) ? current : editions[0].asof;
    selectedAsof = sel.value;
    setQueryAsof(selectedAsof);
  }

  function bindEditionNav() {
    const sel = document.getElementById("edition-select");
    const prev = document.getElementById("edition-prev");
    const next = document.getElementById("edition-next");
    if (!sel || !prev || !next) return;
    sel.addEventListener("change", async () => {
      selectedAsof = sel.value;
      setQueryAsof(selectedAsof);
      await refreshEdition();
    });
    prev.addEventListener("click", async () => {
      const idx = editions.findIndex((e) => e.asof === selectedAsof);
      if (idx >= 0 && idx < editions.length - 1) {
        selectedAsof = editions[idx + 1].asof;
        sel.value = selectedAsof;
        setQueryAsof(selectedAsof);
        await refreshEdition();
      }
    });
    next.addEventListener("click", async () => {
      const idx = editions.findIndex((e) => e.asof === selectedAsof);
      if (idx > 0) {
        selectedAsof = editions[idx - 1].asof;
        sel.value = selectedAsof;
        setQueryAsof(selectedAsof);
        await refreshEdition();
      }
    });
  }

  async function loadArchive() {
    try {
      const r = await fetch("/api/report/archive?limit=90");
      if (!r.ok) return;
      const d = await r.json();
      editions = d.editions || [];
      if (editions.length) loadEditionSelector();
    } catch (_) {
      editions = [];
    }
  }

  function refreshDateline() {
    const lang = window.currentLang || "en";
    const feels = document.getElementById("dateline-feels");
    if (!feels) return;
    const date = window.__npAnalogDate || "March 14, 2000";
    const prefix = lang === "zh" ? "今日情势令人想起 " : lang === "ms" ? "Hari ini terasa seperti " : "Today feels like ";
    feels.textContent = prefix + date;
  }

  window.refreshDateline = refreshDateline;

  async function loadHighlights() {
    try {
      const r = await fetch(apiUrl("/api/report/highlights"));
      if (!r.ok) return;
      const d = await r.json();
      if (d.asof) {
        selectedAsof = d.asof;
        setQueryAsof(selectedAsof);
        const sel = document.getElementById("edition-select");
        if (sel) sel.value = selectedAsof;
      }
      if (d.analog_date) {
        window.__npAnalogDate = d.analog_date;
        refreshDateline();
      }
    } catch (_) { /* static fallback */ }
  }

  async function loadAccessBadge() {
    const el = document.getElementById("access-badge");
    if (!el) return;
    try {
      const r = await fetch(apiUrl("/api/dashboard"));
      if (!r.ok) return;
      const d = await r.json();
      const paid = ["report", "briefing", "agent"].includes(d.tier);
      el.textContent = paid
        ? "Subscriber access: full edition history and latest timestamped report graph."
        : "Free access: historical editions available. Latest intraday trigger board is in subscriber brief.";
      if (d.score?.delayed) {
        el.textContent = `Showing ${d.score.asof}. Free access includes older editions; subscriber access includes latest edition and trigger board.`;
      }
    } catch (_) { /* keep static */ }
  }

  async function loadLiveScore() {
    try {
      const r = await fetch(apiUrl("/api/latest"));
      if (!r.ok) return;
      const d = await r.json();
      if (d.crs !== undefined) {
        document.getElementById("live-crs").textContent = Number(d.crs).toFixed(1);
      }
      const bandEl = document.querySelector(".score-item .score-sub");
      if (bandEl && d.band) bandEl.textContent = d.band.toUpperCase();
      if (d.phase) {
        const phaseEl = document.querySelector('[data-i18n="phase_val"]');
        if (phaseEl) phaseEl.textContent = String(d.phase).replaceAll("_", " ");
      }
      if (d.coverage !== undefined) {
        const pct = (d.coverage * 100).toFixed(0);
        document.querySelectorAll(".caveat").forEach((el) => {
          if (el.textContent.includes("Live inputs") || el.textContent.includes("实时输入") || el.textContent.includes("Input langsung")) {
            const base = el.textContent.split(" Current live coverage:")[0].replace(/\.$/, "");
            el.textContent = `${base}. Current live coverage: ${pct}%.`;
          }
        });
      }
      window.__reportAsof = d.asof;
    } catch (_) { /* static fallback */ }
  }

  function setupShare() {
    if (!CC) return;
    document.getElementById("np-share")?.addEventListener("click", async () => {
      const ok = await CC.shareNative(window.__reportAsof, "Cassandra's Daily", "Today's market desk edition.");
      if (!ok) CC.toast("Share unavailable. Use Copy link.");
    });
    document.getElementById("np-copy")?.addEventListener("click", () => CC.copyReportLink(window.__reportAsof));
    document.getElementById("np-print")?.addEventListener("click", () => window.print());
  }

  function handleSubscribe() {
    const email = document.getElementById("news-email")?.value?.trim();
    if (!email || !email.includes("@")) {
      alert("Please enter a valid email.");
      return;
    }
    fetch("/api/digest/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, source: "newspaper" }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) {
          CC?.toast?.(d.message || "Subscribed to free daily edition.");
        } else {
          alert(d.detail || "Signup failed.");
        }
      })
      .catch(() => alert("Signup unavailable. Try again later."));
  }

  async function refreshEdition() {
    await Promise.all([loadLiveScore(), loadHighlights(), loadAccessBadge()]);
  }

  function setupTierPreview() {
    const nav = document.getElementById("tier-preview-nav");
    if (!nav) return;
    const locked = document.querySelector(".locked-wrap");
    const priceEl = document.querySelector(".meta-right");
    const labels = { free: "Free", report: "Report · $4.99", briefing: "Pro · $9.99", agent: "API · $49.99" };
    nav.querySelectorAll("[data-tier]").forEach((btn) => {
      btn.addEventListener("click", () => {
        nav.querySelectorAll("[data-tier]").forEach((b) => b.classList.toggle("on", b === btn));
        const tier = btn.dataset.tier;
        if (locked) locked.hidden = tier !== "free";
        if (priceEl) priceEl.textContent = labels[tier] || "Free";
      });
    });
  }

  window.handleSubscribe = handleSubscribe;
  setupShare();
  setupTierPreview();
  loadArchive().then(() => {
    bindEditionNav();
    refreshEdition();
  });
})();
