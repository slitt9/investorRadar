"use client";

import * as React from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useMarkets } from "./api";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatUsd } from "@/lib/format";

function InstrumentRow({
  name,
  symbol,
  price,
  pct_change,
  change,
}: {
  name: string;
  symbol: string;
  price: number;
  change: number;
  pct_change: number;
}) {
  const up = pct_change >= 0;
  return (
    <div className="flex items-center justify-between rounded-2xl border border-border/25 bg-[rgb(var(--surface-2)/0.25)] px-3 py-2 transition-colors hover:bg-[rgb(var(--surface-2)/0.45)]">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold tracking-tight">{name}</div>
        <div className="text-xs text-muted">{symbol}</div>
      </div>
      <div className="text-right">
        <div className="text-sm font-semibold tabular-nums">{formatUsd(price)}</div>
        <div
          className={cn(
            "flex items-center justify-end gap-1 text-xs font-semibold tabular-nums",
            up ? "text-emerald" : "text-rose",
          )}
        >
          {up ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
          <span>
            {up ? "+" : ""}
            {pct_change.toFixed(2)}%
          </span>
          <span className="text-muted">
            ({up ? "+" : ""}
            {change.toFixed(2)})
          </span>
        </div>
      </div>
    </div>
  );
}

function GroupCard({ title, items }: { title: string; items: ReturnType<typeof useMarkets>["data"] }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold tracking-tight">{title}</div>
        <div className="text-xs text-muted">{items?.length ?? 0} instruments</div>
      </div>
      <div className="mt-3 grid gap-2">
        {(items ?? []).map((m) => (
          <InstrumentRow
            key={m.symbol}
            name={m.name}
            symbol={m.symbol}
            price={m.price}
            change={m.change}
            pct_change={m.pct_change}
          />
        ))}
      </div>
    </Card>
  );
}

export function MarketsView() {
  const markets = useMarkets();

  const grouped = React.useMemo(() => {
    const data = markets.data ?? [];
    const groups: Record<string, typeof data> = {};
    for (const m of data) {
      (groups[m.group] ||= []).push(m);
    }
    return groups;
  }, [markets.data]);

  return (
    <div className="p-4 lg:p-6">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-xs text-muted">Markets</div>
          <div className="mt-1 text-2xl font-semibold tracking-tight">
            Multi-asset snapshot.
          </div>
          <div className="mt-2 max-w-[70ch] text-sm text-muted">
            Futures, global indices, ETFs, and crypto (powered by yfinance).
          </div>
        </div>
        <div className="text-xs text-muted">
          {markets.isFetching ? "Refreshing…" : "Live-ish"}
        </div>
      </div>

      {markets.isError ? (
        <Card className="p-6 text-sm text-muted">
          Unable to load markets. Start the backend API (Flask) or set{" "}
          <span className="text-foreground">NEXT_PUBLIC_API_BASE_URL</span>.
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <GroupCard title="Futures" items={grouped.Futures} />
          <GroupCard title="Crypto" items={grouped.Crypto} />
          <GroupCard title="Global" items={grouped.Global} />
          <GroupCard title="ETFs" items={grouped.ETFs} />
        </div>
      )}
    </div>
  );
}
