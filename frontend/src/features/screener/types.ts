export type ScreenerFilters = {
  marketCap: [number, number]; // USD
  pe: [number, number];
  volume: [number, number];
  sector:
    | "All"
    | "Technology"
    | "Financials"
    | "Healthcare"
    | "Energy"
    | "Consumer"
    | "Industrials";
  price: [number, number];
};

export type ScreenerRow = {
  ticker: string;
  company_name: string;
  price: number;
  pct_change: number; // percent (backend)
  volume: number;
  market_cap: number | null;
  pe_ratio: number | null;
  sector: string;
  industry: string;
  dividend_yield: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  radar_pulse?: number | null;
};

export type SeriesPoint = { t: number; v: number };
