function renderStock(ticker) {
  const d = window.STOCK_DEMO?.[ticker];
  const el = document.getElementById("stock-app");
  if (!d || !el) return;
  el.innerHTML = `
    <div class="stock-header">
      <div class="stock-ticker">${d.ticker}</div>
      <div class="stock-name">${d.name}</div>
      <div class="stock-crs">${d.crs_stock}</div>
      <div class="stock-band">${d.band} zone · stock-specific CRS (demo)</div>
    </div>
    <section class="stock-section">
      <h2>Fragility drivers</h2>
      <ul>${d.fragility_drivers.map((x) => `<li>${x}</li>`).join("")}</ul>
    </section>
    <section class="stock-section">
      <h2>Trigger watch</h2>
      <ul>${d.trigger_watch.map((x) => `<li>${x}</li>`).join("")}</ul>
    </section>
    <section class="stock-section">
      <h2>Nearest analog</h2>
      <p>${d.analog}</p>
      <p class="stock-note">${d.note}</p>
    </section>
    <a class="btn btn-primary stock-cta" href="/subscribe?tier=agent">Subscribe at $50/mo for live stock agents</a>`;
}
