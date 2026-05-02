"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import type { ScreenerFilters, ScreenerRow } from "./types";
import { apiGet } from "@/lib/api";

const UI_MAX_MARKET_CAP = 2_000_000_000_000;
const UI_MAX_PE = 80;
const UI_MAX_VOLUME = 100_000_000;
const UI_MAX_PRICE = 600;
const FAST_PATH_MARKET_CAP_MIN = 1_000_000_000_000;

function isWideOpen(filters: ScreenerFilters) {
  return (
    filters.query.trim().length === 0 &&
    filters.sector === "All" &&
    filters.marketCap[0] <= 0 &&
    filters.marketCap[1] >= UI_MAX_MARKET_CAP &&
    filters.pe[0] <= 0 &&
    filters.pe[1] >= UI_MAX_PE &&
    filters.volume[0] <= 0 &&
    filters.volume[1] >= UI_MAX_VOLUME &&
    filters.price[0] <= 0 &&
    filters.price[1] >= UI_MAX_PRICE
  );
}

function isMegaCapFastPath(filters: ScreenerFilters) {
  return (
    filters.query.trim().length === 0 &&
    filters.sector === "All" &&
    filters.marketCap[0] >= FAST_PATH_MARKET_CAP_MIN &&
    filters.marketCap[1] >= UI_MAX_MARKET_CAP &&
    filters.pe[0] <= 0 &&
    filters.pe[1] >= UI_MAX_PE &&
    filters.volume[0] <= 0 &&
    filters.volume[1] >= UI_MAX_VOLUME &&
    filters.price[0] <= 0 &&
    filters.price[1] >= UI_MAX_PRICE
  );
}

async function fetchScreener(filters: ScreenerFilters): Promise<ScreenerRow[]> {
  const megaCapFastPath = isMegaCapFastPath(filters);
  return apiGet<ScreenerRow[]>("/api/screener", {
    universe: megaCapFastPath ? "mega" : "sp500",
    q: filters.query,
    sector: filters.sector,
    market_cap_min: filters.marketCap[0],
    market_cap_max: filters.marketCap[1],
    pe_min: filters.pe[0],
    pe_max: filters.pe[1],
    volume_min: filters.volume[0],
    volume_max: filters.volume[1],
    price_min: filters.price[0],
    price_max: filters.price[1],
    limit: megaCapFastPath ? 60 : isWideOpen(filters) ? 180 : 120,
  });
}

export function useScreenerResults(appliedFilters: ScreenerFilters) {
  return useQuery({
    queryKey: ["screener-results", appliedFilters],
    queryFn: () => fetchScreener(appliedFilters),
  });
}

export function useScreenerFilters() {
  const initial: ScreenerFilters = React.useMemo(
    () => ({
      query: "",
      marketCap: [FAST_PATH_MARKET_CAP_MIN, UI_MAX_MARKET_CAP],
      pe: [0, UI_MAX_PE],
      volume: [0, UI_MAX_VOLUME],
      sector: "All",
      price: [0, UI_MAX_PRICE],
    }),
    [],
  );

  const [draft, setDraft] = React.useState<ScreenerFilters>(initial);
  const [applied, setApplied] = React.useState<ScreenerFilters>(initial);

  return {
    initial,
    draft,
    setDraft,
    applied,
    apply: () => setApplied(draft),
    reset: () => {
      setDraft(initial);
      setApplied(initial);
    },
  };
}
