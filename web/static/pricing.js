const TIERS = [
  { id: "free", name: "Free", price: "$0", features: ["Live CRS + band", "L + V factors", "3× daily updates", "Email summary"], cta: "Access now →", href: "/" },
  { id: "report", name: "The Report", price: "$4.99/mo", features: ["Full 5-factor report", "Newspaper daily email", "Historical analog", "capex NLP detail"], cta: "Subscribe →", href: "/subscribe?tier=report", popular: false },
  { id: "briefing", name: "The Briefing", price: "$10/mo", features: ["10-page deep analysis", "AI insights (Gemini)", "2000/2008 analog side-by-side", "Source attribution"], cta: "Subscribe →", href: "/subscribe?tier=briefing", popular: true },
  { id: "agent", name: "The Agent", price: "$50/mo", features: ["Custom watchlist", "Stock CRS demos → live", "API JSON access", "Chat 50/day"], cta: "Subscribe →", href: "/subscribe?tier=agent" },
];

async function init() {
  CassandraCommon.initTheme(true);
  document.getElementById("theme-toggle").onclick = () => CassandraCommon.toggleTheme();
  const params = new URLSearchParams(location.search);
  const ref = params.get("ref") || CassandraCommon.referralCode();
  const grid = document.getElementById("tier-grid");
  grid.innerHTML = TIERS.map((t) => `
    <div class="tier-card${t.popular ? " popular" : ""}">
      ${t.popular ? '<span class="tier-badge">MOST POPULAR</span>' : ""}
      <div class="tier-name">${t.name}</div>
      <div class="tier-price">${t.price}</div>
      <div class="video-ph">▶ Demo video placeholder</div>
      <ul>${t.features.map((f) => `<li>${f}</li>`).join("")}</ul>
      <a class="btn btn-primary" href="${t.href}${t.id !== "free" ? `&ref=${ref}` : ""}">${t.cta}</a>
    </div>`).join("");
}
init();
