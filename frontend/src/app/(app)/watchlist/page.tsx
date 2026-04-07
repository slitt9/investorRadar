"use client";

import * as React from "react";
import Link from "next/link";
import { Star, Trash2 } from "lucide-react";
import { useWatchlist } from "@/features/watchlist/watchlist-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function WatchlistPage() {
  const watchlist = useWatchlist();

  return (
    <div className="p-4 lg:p-6">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-xs text-muted">Watchlist</div>
          <div className="mt-1 text-2xl font-semibold tracking-tight">
            Stars you care about.
          </div>
          <div className="mt-2 text-sm text-muted">
            Stored locally in your browser (localStorage).
          </div>
        </div>
        <Button
          variant="danger"
          onClick={watchlist.clear}
          disabled={watchlist.tickers.length === 0}
        >
          <Trash2 className="h-4 w-4" />
          Clear
        </Button>
      </div>

      {watchlist.tickers.length === 0 ? (
        <Card className="p-6 text-sm text-muted">
          No watchlist items yet. Go to{" "}
          <Link href="/screener" className="text-foreground underline">
            Screener
          </Link>{" "}
          and star a stock.
        </Card>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {watchlist.tickers.map((t) => (
            <Card key={t} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-muted">Ticker</div>
                  <div className="mt-1 text-lg font-semibold tracking-tight">
                    {t}
                  </div>
                </div>
                <button
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-[rgb(var(--blue)/0.95)] fill-[rgb(var(--blue)/0.30)] transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                  onClick={() => watchlist.toggle(t)}
                  aria-label="Remove from watchlist"
                >
                  <Star className="h-4 w-4 fill-[rgb(var(--blue)/0.30)]" />
                </button>
              </div>
              <div className="mt-4">
                <Button asChild variant="primary" className="w-full">
                  <Link href={`/screener?ticker=${encodeURIComponent(t)}`}>
                    Open
                  </Link>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
