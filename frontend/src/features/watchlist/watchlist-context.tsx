"use client";

import * as React from "react";

const STORAGE_KEY = "investorradar.watchlist.v1";

type WatchlistContextValue = {
  tickers: string[];
  has: (ticker: string) => boolean;
  add: (ticker: string) => void;
  remove: (ticker: string) => void;
  toggle: (ticker: string) => void;
  clear: () => void;
};

const WatchlistContext = React.createContext<WatchlistContextValue | null>(null);

function normalize(ticker: string) {
  return ticker.trim().toUpperCase();
}

function readFromStorage(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalize).filter(Boolean);
  } catch {
    return [];
  }
}

function writeToStorage(tickers: string[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
  } catch {
    // ignore
  }
}

export function WatchlistProvider({ children }: { children: React.ReactNode }) {
  const [tickers, setTickers] = React.useState<string[]>(() => readFromStorage());

  React.useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY) return;
      setTickers(readFromStorage());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const api = React.useMemo<WatchlistContextValue>(() => {
    function set(next: string[]) {
      const uniq = Array.from(new Set(next.map(normalize))).filter(Boolean).sort();
      setTickers(uniq);
      writeToStorage(uniq);
    }

    return {
      tickers,
      has: (t) => tickers.includes(normalize(t)),
      add: (t) => set([...tickers, normalize(t)]),
      remove: (t) => set(tickers.filter((x) => x !== normalize(t))),
      toggle: (t) => {
        const n = normalize(t);
        set(tickers.includes(n) ? tickers.filter((x) => x !== n) : [...tickers, n]);
      },
      clear: () => set([]),
    };
  }, [tickers]);

  return (
    <WatchlistContext.Provider value={api}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = React.useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used within WatchlistProvider");
  return ctx;
}

