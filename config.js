/** CASSANDRA  -  public dashboard config (no secrets). */
window.CASSANDRA_CONFIG = window.CASSANDRA_CONFIG || {};
Object.assign(window.CASSANDRA_CONFIG, {
  version: "0.9.0-deploy",
  contactTo: "desk@netie.ai",
  brand: {
    site: "https://crash.netie.ai",
    org: "https://netie.ai",
    github: "https://github.com/Netie-AI/Cassandra",
  },
  newsletterAction: "",
  payments: {
    international: {
      stripeSubscribe: "",   // fallback alias for Report tier
      stripeReport: "https://buy.stripe.com/fZu5kDchg1y35fK8D29ws00",
      stripeBriefing: "https://buy.stripe.com/bJe14n9541y3dMgbPe9ws01",
      stripeAgent: "https://buy.stripe.com/14AfZhbdc90v9w02eE9ws02",
      stripeDonate: "",
      paypalDonate: "",
    },
    my: {
      billplzReport: "",     // FILL: Billplz collection URL, Report
      billplzBriefing: "",   // FILL: Billplz collection URL, Pro
      curlecSubscribe: "",
      billplzDonate: "",
    },
    cn: {
      airwallexReport: "",   // FILL: Airwallex payment URL, Report
      airwallexSubscribe: "",
      airwallexDonate: "",
    },
  },
  // Aliases for validation (mirror payments.international)
  stripe_report_url: "https://buy.stripe.com/fZu5kDchg1y35fK8D29ws00",
  stripe_pro_url: "https://buy.stripe.com/bJe14n9541y3dMgbPe9ws01",
  stripe_api_url: "https://buy.stripe.com/14AfZhbdc90v9w02eE9ws02",
});

(function syncStripeAliases() {
  const p = window.CASSANDRA_CONFIG.payments?.international || {};
  const c = window.CASSANDRA_CONFIG;
  c.stripe_report_url = c.stripe_report_url || p.stripeReport || p.stripeSubscribe || "";
  c.stripe_pro_url = c.stripe_pro_url || p.stripeBriefing || "";
  c.stripe_api_url = c.stripe_api_url || p.stripeAgent || "";
})();

(function validateConfig() {
  const c = window.CASSANDRA_CONFIG;
  const gaps = [];
  if (!c.stripe_report_url) gaps.push("stripe_report_url");
  if (!c.stripe_pro_url) gaps.push("stripe_pro_url");
  if (!c.stripe_api_url) gaps.push("stripe_api_url");
  if (gaps.length) {
    console.warn("[Cassandra] Payment URLs not configured:", gaps);
    if (window.location.hostname === "localhost") {
      document.addEventListener("DOMContentLoaded", () => {
        const b = document.createElement("div");
        b.style.cssText =
          "position:fixed;bottom:0;left:0;right:0;background:#b45309;color:#fff;padding:8px;font-size:12px;z-index:9999;text-align:center;";
        b.textContent = `[DEV] Payment URLs missing: ${gaps.join(", ")} - fill config.js`;
        document.body.appendChild(b);
      });
    }
  }
  c._paymentGaps = gaps;
})();
