"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

export type MarketInstrument = {
  symbol: string;
  name: string;
  group: "Futures" | "Global" | "Crypto" | "ETFs" | string;
  price: number;
  change: number;
  pct_change: number;
};

export function useMarkets() {
  return useQuery({
    queryKey: ["markets"],
    queryFn: () => apiGet<MarketInstrument[]>("/api/markets"),
    staleTime: 30_000,
  });
}

