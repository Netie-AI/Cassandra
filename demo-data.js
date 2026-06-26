/** Hardcoded demo payloads  -  used when /api/* is unreachable (static Pages deploy). */
window.CassandraDemo = {
  movers: {
    "1D": {
      scale: 14,
      movers: [
        { sym: "MU", pct: 8.6 }, { sym: "WDC", pct: 7.2 }, { sym: "SMCI", pct: -12.4 },
        { sym: "ARM", pct: 8.2 }, { sym: "MSTR", pct: -6.1 }, { sym: "AVGO", pct: 5.8 },
        { sym: "AMD", pct: -4.3 }, { sym: "CRWD", pct: 3.1 }, { sym: "NVDA", pct: 2.4 },
        { sym: "KLAC", pct: -2.8 },
      ],
    },
    "5D": {
      scale: 16,
      movers: [
        { sym: "ARM", pct: 14.2 }, { sym: "SMCI", pct: -11.8 }, { sym: "MSTR", pct: -9.4 },
        { sym: "AVGO", pct: 8.1 }, { sym: "NVDA", pct: 6.2 }, { sym: "AMD", pct: -5.4 },
        { sym: "CRWD", pct: 4.8 }, { sym: "KLAC", pct: -3.9 }, { sym: "AMAT", pct: -3.1 },
        { sym: "TSM", pct: 2.4 },
      ],
    },
    "1M": {
      scale: 30,
      movers: [
        { sym: "MU", pct: 28.4 }, { sym: "WDC", pct: 24.1 }, { sym: "ARM", pct: 28.4 },
        { sym: "MSTR", pct: -22.1 }, { sym: "SMCI", pct: -19.8 }, { sym: "AVGO", pct: 18.6 },
        { sym: "CRWD", pct: 15.2 }, { sym: "NVDA", pct: 12.4 }, { sym: "AMD", pct: -10.1 },
        { sym: "KLAC", pct: -8.4 },
      ],
    },
  },
  indices: [
    { sym: "SPX", val: "5,634", pct: -0.42 },
    { sym: "NDX", val: "19,847", pct: -0.61 },
    { sym: "VIX", val: "18.24", pct: 5.2 },
    { sym: "SOX", val: "4,312", pct: -1.18 },
  ],
  fearGreed: {
    value: 42,
    label: "Fear",
    color: "#B91C1C",
    source: "demo_proxy",
    spark: [49, 49, 48, 49, 49, 48, 48, 48, 47, 48, 48, 48, 47, 46, 47, 48, 48, 48, 48, 48, 47, 47, 48, 49, 49, 49, 49, 49],
  },
  watchlist: [
    { sym: "LEU", px: "80.14", pct: 3.21 },
    { sym: "NVDA", px: "118.42", pct: 2.41 },
    { sym: "MSFT", px: "438.71", pct: 0.94 },
    { sym: "AMZN", px: "214.08", pct: -0.38 },
    { sym: "TSM", px: "191.55", pct: 1.12 },
  ],
};
