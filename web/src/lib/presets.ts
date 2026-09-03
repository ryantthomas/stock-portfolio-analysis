/** Starting points so a new user can see a real analysis in one click. */

export interface Preset {
  name: string;
  description: string;
  holdings: { ticker: string; weight: number }[];
}

export const PRESETS: Preset[] = [
  {
    name: "Three-fund",
    description: "US equity, international equity and bonds. The classic lazy portfolio.",
    holdings: [
      { ticker: "VTI", weight: 50 },
      { ticker: "VXUS", weight: 30 },
      { ticker: "BND", weight: 20 },
    ],
  },
  {
    name: "60/40",
    description: "Sixty percent equities, forty percent bonds.",
    holdings: [
      { ticker: "VOO", weight: 60 },
      { ticker: "BND", weight: 40 },
    ],
  },
  {
    name: "All weather",
    description: "Ray Dalio's allocation, built to hold up across economic regimes.",
    holdings: [
      { ticker: "VTI", weight: 30 },
      { ticker: "TLT", weight: 40 },
      { ticker: "SHY", weight: 15 },
      { ticker: "GLD", weight: 7.5 },
      { ticker: "DBC", weight: 7.5 },
    ],
  },
  {
    name: "Big tech",
    description: "Concentrated mega-cap technology. A useful example of what over-concentration looks like.",
    holdings: [
      { ticker: "AAPL", weight: 20 },
      { ticker: "MSFT", weight: 20 },
      { ticker: "NVDA", weight: 20 },
      { ticker: "GOOGL", weight: 20 },
      { ticker: "AMZN", weight: 20 },
    ],
  },
  {
    name: "Dividend income",
    description: "Dividend-focused equity with a bond and REIT sleeve.",
    holdings: [
      { ticker: "SCHD", weight: 35 },
      { ticker: "VYM", weight: 25 },
      { ticker: "VNQ", weight: 15 },
      { ticker: "LQD", weight: 15 },
      { ticker: "TIP", weight: 10 },
    ],
  },
];
