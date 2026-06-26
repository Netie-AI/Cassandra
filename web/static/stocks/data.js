window.STOCK_DEMO = {
  MU: {
    ticker: "MU",
    name: "Micron Technology",
    sector: "semis / hardware",
    px: "1,013.80",
    pct: -13.2,
    crs_stock: 63.4,
    band: "Danger",
    band_color: "#C2410C",
    fragility_drivers: [
      "DRAM pricing at cycle peak, +48% YoY",
      "HBM capacity sold out through 2026",
      "Capex/revenue ratio elevated vs 5-yr median",
    ],
    trigger_watch: [
      "Hyperscaler HBM order pace",
      "China demand / export controls",
      "DRAM spot price rollover risk",
    ],
    analog: "Micron Q2 2018  -  5 months before the -45% memory-cycle drawdown",
    targets: {
      updated: "24 Jun 2026",
      jpmorgan: { price: 1100, stance: "Overweight", date: "Jun 2026" },
      morningstar: { fv: 890, stance: "Fair Value", date: "Jun 2026" },
      capex_score: 0.35,
    },
    premium: {
      frag_quant: [
        { n: "P/S ratio", v: "4.8×", d: "vs 3.1× median" },
        { n: "Insider sell/buy", v: "3.6×", d: "above average" },
        { n: "AI rev dependency", v: "42%", d: "of fwd guidance" },
        { n: "Short interest", v: "2.1%", d: "rising" },
      ],
      levels: [
        { n: "Resistance", v: "$102", m: "cycle high" },
        { n: "Support", v: "$88", m: "50-day" },
        { n: "Invalidation", v: "$81", m: "thesis breaks" },
      ],
      changelog: [
        { t: "CRS 61.0 → 63.4", d: "DRAM spot ticked down 1.2%", c: "#B91C1C" },
        { t: "Insider filing", d: "Form 4: VP sold 12k shares", c: "#C2410C" },
        { t: "Analog shifted", d: "now Q2 2018 (was Q4 2021)", c: "#92400E" },
      ],
      similarity: {
        score: 0.81,
        window: "March 2000",
        matches: [
          { src: "WSJ · \"Chip demand seen insatiable\"", date: "Mar 2000", sim: "0.89", url: "#" },
          { src: "Barron's · \"Memory glut fears overblown\"", date: "Feb 2000", sim: "0.84", url: "#" },
          { src: "Reuters · capex guidance raised", date: "Jan 2000", sim: "0.78", url: "#" },
        ],
      },
    },
    note: "Demo only. Premium unlocks sourced comparables and live change-log.",
    editions: [
      { date: "2026-06-24", available: false },
      { date: "2026-06-20", available: true },
      { date: "2026-06-17", available: false },
      { date: "2026-06-12", available: false },
    ],
  },
  NOW: {
    ticker: "NOW",
    name: "ServiceNow",
    sector: "enterprise software",
    px: "946.20",
    pct: -2.48,
    crs_stock: 51.2,
    band: "Mania",
    band_color: "#C2410C",
    fragility_drivers: [
      "P/S ratio at 18× vs 5-year median 14×",
      "Insider sell ratio: 4.2× above average",
      "AI revenue dependency: 38% of forward guidance",
    ],
    trigger_watch: [
      "Enterprise IT spend freeze signals",
      "Azure/AWS growth deceleration as demand proxy",
      "Fed rate path impact on SaaS multiples",
    ],
    analog: "Salesforce Q2 2022  -  6 weeks before -55% drawdown",
    targets: {
      updated: "24 Jun 2026",
      jpmorgan: { price: 920, stance: "Neutral", date: "Jun 2026" },
      morningstar: { fv: 780, stance: "Fair Value", date: "Jun 2026" },
      capex_score: 0.42,
    },
    premium: {
      frag_quant: [
        { n: "P/S ratio", v: "18.1×", d: "vs 14× median" },
        { n: "Insider sell/buy", v: "4.2×", d: "above average" },
        { n: "AI rev dependency", v: "38%", d: "of fwd guidance" },
        { n: "Short interest", v: "1.4%", d: "stable" },
      ],
      levels: [
        { n: "Resistance", v: "$845", m: "52-week high" },
        { n: "Support", v: "$780", m: "200-day" },
        { n: "Invalidation", v: "$740", m: "thesis breaks" },
      ],
      changelog: [
        { t: "CRS 49.8 → 51.2", d: "IT budget survey softened", c: "#C2410C" },
        { t: "Trigger watch", d: "Azure growth decel headline", c: "#92400E" },
        { t: "Sentiment delta", d: "vs Mar 2000 analog: -0.3", c: "#B91C1C" },
      ],
      similarity: {
        score: 0.74,
        window: "March 2000",
        matches: [
          { src: "WSJ · \"Enterprise software seen unstoppable\"", date: "Feb 2000", sim: "0.82", url: "#" },
          { src: "Barron's · \"SaaS multiples justified by growth\"", date: "Jan 2000", sim: "0.76", url: "#" },
          { src: "Reuters · IT budget survey strong", date: "Mar 2000", sim: "0.71", url: "#" },
        ],
      },
    },
    note: "Demo only. Premium unlocks sourced comparables and live change-log.",
    editions: [
      { date: "2026-06-24", available: false },
      { date: "2026-06-20", available: true },
      { date: "2026-06-17", available: false },
      { date: "2026-06-12", available: false },
    ],
  },
};
