/** CASSANDRA — public dashboard config (no secrets). */
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
      stripeReport: "",      // FILL: Stripe payment link, Report tier
      stripeBriefing: "",    // FILL: Stripe payment link, Pro tier
      stripeAgent: "",       // FILL: Stripe payment link, API tier
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
});
