"use client";

import { cn } from "@/lib/cn";
import { formatUsd } from "@/lib/format";
import type { MoversResponse, MoversRow } from "../api";

function MoversTable({
  title,
  rows,
  positive,
}: {
  title: string;
  rows: MoversRow[];
  positive: boolean;
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] p-4 backdrop-blur">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold tracking-tight">{title}</div>
        <div
          className={cn("text-xs font-medium", positive ? "text-emerald" : "text-rose")}
        >
          {positive ? "Gainers" : "Losers"}
        </div>
      </div>
      <div className="mt-3 grid gap-2">
        {rows.slice(0, 6).map((r) => (
          <div
            key={r.ticker}
            className="flex items-center justify-between rounded-xl border border-border/25 bg-[rgb(var(--surface-2)/0.25)] px-3 py-2 transition-colors hover:bg-[rgb(var(--surface-2)/0.45)]"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="text-sm font-semibold tracking-tight">{r.ticker}</div>
                <div className="truncate text-xs text-muted">
                  Vol {r.volume.toLocaleString()}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted">{formatUsd(r.price)}</div>
              <div
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  positive ? "text-emerald" : "text-rose",
                )}
              >
                {r.pct_change >= 0 ? "+" : ""}
                {r.pct_change.toFixed(2)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Movers({ movers }: { movers: MoversResponse }) {
  const gainers = movers.gainers ?? [];
  const losers = movers.losers ?? [];

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <MoversTable title="Top Movers" rows={gainers} positive />
      <MoversTable title="Top Movers" rows={losers} positive={false} />
    </div>
  );
}
