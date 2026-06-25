/** Newspaper report — live score, share, download */
(function () {
  const CC = window.CassandraCommon;

  async function loadLiveScore() {
    try {
      const r = await fetch("/api/latest");
      if (!r.ok) return;
      const d = await r.json();
      if (d.crs !== undefined) {
        document.getElementById("live-crs").textContent = Number(d.crs).toFixed(1);
      }
      const bandEl = document.querySelector(".score-item .score-sub");
      if (bandEl && d.band) bandEl.textContent = d.band.toUpperCase();
      if (d.fragility !== undefined) {
        const fEl = document.querySelectorAll(".score-val")[1];
        if (fEl) fEl.textContent = Number(d.fragility).toFixed(2);
      }
      if (d.trigger !== undefined) {
        const tEl = document.querySelectorAll(".score-val")[2];
        if (tEl) tEl.textContent = Number(d.trigger).toFixed(2);
      }
      if (d.coverage !== undefined) {
        const pct = (d.coverage * 100).toFixed(0);
        document.querySelectorAll(".caveat").forEach((el) => {
          if (el.textContent.includes("Coverage")) {
            el.textContent = el.textContent.replace(/\d+%/, `${pct}%`);
          }
        });
      }
      window.__reportAsof = d.asof;
    } catch (_) { /* static fallback */ }
  }

  function setupShare() {
    const bar = document.getElementById("share-bar");
    if (!bar || !CC) return;
    document.getElementById("np-copy")?.addEventListener("click", () => {
      CC.shareReport(window.__reportAsof);
    });
    document.getElementById("np-download")?.addEventListener("click", () => {
      const asof = window.__reportAsof || new Date().toISOString().slice(0, 10);
      CC.downloadHtml(`cassandra-report-${asof}.html`);
      CC.toast("Download started");
    });
    document.getElementById("np-print")?.addEventListener("click", () => window.print());
  }

  function handleSubscribe() {
    const email = document.getElementById("news-email")?.value?.trim();
    if (!email || !email.includes("@")) {
      alert("Please enter a valid email address.");
      return;
    }
    const ref = CC?.referralCode?.() || "";
    window.location.href = `/subscribe?email=${encodeURIComponent(email)}&ref=${ref}`;
  }

  window.handleSubscribe = handleSubscribe;
  loadLiveScore();
  setupShare();
})();
