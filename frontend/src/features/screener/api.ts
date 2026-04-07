"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

export type QuoteMetrics = {
  ticker: string;
  company_name: string;
  sector: string;
  industry: string;
  price: number;
  change: number | null;
  pct_change: number;
  market_cap: number | null;
  volume: number | null;
  pe_ratio: number | null;
  ps_ratio: number | null;
  enterprise_value: number | null;
  profit_margin: number | null;
  roe: number | null;
  dividend_yield: number | null;
  payout_ratio: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  quarterly_revenue_growth: number | null;
  assets: number | null;
  liabilities: number | null;
  equity: number | null;
  radar_pulse?: number | null;
};

export type HistoryPoint = {
  Date: string;
  Open: number;
  High: number;
  Low: number;
  Close: number;
  Volume: number;
};

export type MoversRow = {
  ticker: string;
  price: number;
  change: number;
  pct_change: number;
  volume: number;
};

export type MoversResponse = {
  gainers: MoversRow[];
  losers: MoversRow[];
};

export type SearchResult = {
  ticker: string;
  name: string;
  cik?: string;
};

export function useQuote(ticker: string | null) {
  return useQuery({
    queryKey: ["quote", ticker],
    enabled: Boolean(ticker),
    queryFn: () => apiGet<QuoteMetrics>(`/api/quote/${ticker}`),
    staleTime: 10_000,
  });
}

export function useSparkline(ticker: string | null) {
  return useQuery({
    queryKey: ["sparkline", ticker],
    enabled: Boolean(ticker),
    queryFn: () => apiGet<number[]>(`/api/sparkline/${ticker}`),
    staleTime: 10_000,
  });
}

export function useHistory(
  ticker: string | null,
  params: { period: string; interval: string },
) {
  return useQuery({
    queryKey: ["history", ticker, params],
    enabled: Boolean(ticker),
    queryFn: () =>
      apiGet<HistoryPoint[]>(`/api/history/${ticker}`, {
        period: params.period,
        interval: params.interval,
      }),
    staleTime: 10_000,
  });
}

export function useMovers() {
  return useQuery({
    queryKey: ["movers"],
    queryFn: () => apiGet<MoversResponse>("/api/movers"),
    staleTime: 30_000,
  });
}

export function useSearch(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["search", q],
    enabled: q.length >= 1,
    queryFn: () => apiGet<SearchResult[]>("/api/search", { q }),
    staleTime: 30_000,
  });
}
