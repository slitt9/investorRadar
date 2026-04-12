"use client";

import * as React from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { AnimatedNumber } from "@/components/animated-number";
import { cn } from "@/lib/cn";
import { formatCompactNumber, formatPercent, formatUsd } from "@/lib/format";
import { StockSparkline } from "./stock-sparkline";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useHistory, useQuote, useSparkline } from "../api";
import type { SeriesPoint } from "../types";
import { Star } from "lucide-react";
import { useWatchlist } from "@/features/watchlist/watchlist-context";

function RangeBar({ low, high, value }: { low: number; high: number; value: number }) {
  const pct = Math.max(0, Math.min(1, (value - low) / Math.max(1, high - low)));
  return (
    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[rgb(var(--surface-2)/0.65)]">
      <div
        className="h-full bg-[linear-gradient(90deg,rgb(var(--blue)/0.70),rgb(var(--purple)/0.60))]"
        style={{ width: `${pct * 100}%` }}
      />
    </div>
  );
}

function BentoStat({ label, value }: { label: string; value: React.ReactNode }) {
  const pulseValue =
    label === "Radar Pulse" && (typeof value === "string" || typeof value === "number")
      ? Number.parseInt(String(value), 10)
      : null;

  const pulse = Number.isFinite(pulseValue)
    ? Math.max(0, Math.min(100, pulseValue as number))
    : null;

  const pulseTone =
    pulse == null
      ? "border-border/30 bg-[rgb(var(--surface-2)/0.25)]"
      : pulse >= 90
        ? "border-[rgb(var(--emerald)/0.35)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.05),rgb(var(--emerald)/0.22))]"
        : pulse >= 75
          ? "border-[rgb(var(--emerald)/0.30)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.06),rgb(var(--emerald)/0.16))]"
          : pulse >= 60
            ? "border-[rgb(var(--blue)/0.35)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.06),rgb(var(--blue)/0.18))]"
            : pulse >= 45
              ? "border-[rgb(var(--blue)/0.30)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.10),rgb(var(--blue)/0.12))]"
              : pulse >= 30
                ? "border-[rgb(var(--rose)/0.25)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.14),rgb(var(--surface-2)/0.14))]"
                : "border-[rgb(var(--rose)/0.35)] bg-[linear-gradient(135deg,rgb(var(--rose)/0.22),rgb(var(--surface-2)/0.12))]";

  const pulseText =
    pulse == null
      ? "text-muted"
      : pulse >= 75
        ? "text-emerald"
        : pulse >= 45
          ? "text-foreground"
          : "text-rose";

  return (
    <div
      className={cn(
        "rounded-2xl border p-3",
        label === "Radar Pulse"
          ? pulseTone
          : "border-border/30 bg-[rgb(var(--surface-2)/0.25)]",
      )}
    >
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 text-sm font-semibold tabular-nums",
          label === "Radar Pulse" && pulse != null && pulseText,
        )}
      >
        {value}
      </div>
    </div>
  );
}

function sparklineToSeries(values: number[]): SeriesPoint[] {
  const now = Date.now();
  const step = 24 * 60 * 60 * 1000;
  return values.map((v, i) => ({
    t: now - (values.length - 1 - i) * step,
    v,
  }));
}

function hasOverviewLabel(value: string | undefined | null): boolean {
  const t = (value ?? "").trim();
  return t.length > 0 && t.toUpperCase() !== "N/A";
}

function formatXAxisLabel(tf: "1W" | "1M" | "1Y" | "MAX", raw: string) {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const opts: Intl.DateTimeFormatOptions =
    tf === "1W"
      ? { weekday: "short", hour: "2-digit", minute: "2-digit" }
      : tf === "1M"
        ? { month: "short", day: "2-digit" }
        : { year: "2-digit", month: "short" };
  return new Intl.DateTimeFormat("en-US", opts).format(d);
}

function Overview({ ticker, fullscreen }: { ticker: string; fullscreen?: boolean }) {
  const quote = useQuote(ticker);
  const sparkline = useSparkline(ticker);
  const watchlist = useWatchlist();

  const m = quote.data;
  const series = React.useMemo(
    () => (sparkline.data ? sparklineToSeries(sparkline.data) : []),
    [sparkline.data],
  );

  if (quote.isError) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] p-6 text-center text-sm text-muted backdrop-blur">
        Unable to load {ticker}.
      </div>
    );
  }

  if (quote.isLoading || !m) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] p-6 text-sm text-muted backdrop-blur">
        Loading…
      </div>
    );
  }

  const up = (m.pct_change ?? 0) >= 0;
  const watched = watchlist.has(m.ticker);
  const sectorIndustry = [m.sector, m.industry]
    .filter(hasOverviewLabel)
    .join(" • ");
  const showCompany = hasOverviewLabel(m.company_name);

  return (
    <div className="grid gap-3">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs text-muted">Overview</div>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <div className="text-2xl font-semibold tracking-tight">{m.ticker}</div>
                {sectorIndustry ? (
                  <Badge variant="info">{sectorIndustry}</Badge>
                ) : null}
                <button
                  className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                  onClick={() => watchlist.toggle(m.ticker)}
                  aria-label={watched ? "Remove from favorites" : "Add to favorites"}
                >
                  <Star
                    className={cn(
                      "h-4 w-4",
                      watched &&
                        "text-[rgb(var(--blue)/0.95)] fill-[rgb(var(--blue)/0.30)]",
                    )}
                  />
                </button>
              </div>
              {showCompany ? (
                <div className="mt-1 text-sm text-muted">{m.company_name}</div>
              ) : null}
              <div className="mt-2 flex items-baseline gap-3">
                <AnimatedNumber
                  value={m.price}
                  format={(n) => formatUsd(n, { maximumFractionDigits: 2 })}
                  className="text-xl font-semibold tabular-nums"
                />
                <div
                  className={cn(
                    "text-sm font-semibold tabular-nums",
                    up ? "text-emerald" : "text-rose",
                  )}
                >
                  {up ? "+" : ""}
                  {Number(m.pct_change ?? 0).toFixed(2)}%
                </div>
              </div>
            </div>
            {series.length > 0 ? (
              <StockSparkline
                data={series}
                color={up ? "rgb(var(--emerald))" : "rgb(var(--rose))"}
              />
            ) : (
              <div className="h-10 w-[140px] rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.25)]" />
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-2 gap-2">
            <BentoStat
              label="Radar Pulse"
              value={m.radar_pulse != null ? `${m.radar_pulse}/100` : "—"}
            />
            <BentoStat
              label="Market Cap"
              value={m.market_cap ? formatCompactNumber(m.market_cap) : "—"}
            />
            <BentoStat
              label="Volume"
              value={m.volume ? formatCompactNumber(m.volume) : "—"}
            />
            <BentoStat label="P/E" value={m.pe_ratio ? m.pe_ratio.toFixed(2) : "—"} />
            <BentoStat
              label="Dividend Yield"
              value={
                m.dividend_yield != null
                  ? formatPercent(m.dividend_yield, { maximumFractionDigits: 2 })
                  : "—"
              }
            />
          </div>
        </CardContent>
      </Card>

      <Chart ticker={ticker} fullscreen={fullscreen} />

      <motion.div whileHover={{ scale: 1.01 }} transition={{ duration: 0.18 }}>
        <div className="grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardHeader>
                <CardTitle>Valuation</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2">
                <BentoStat label="P/S" value={m.ps_ratio != null ? m.ps_ratio.toFixed(2) : "—"} />
                <BentoStat
                  label="EV"
                  value={m.enterprise_value ? formatCompactNumber(m.enterprise_value) : "—"}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Efficiency</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2">
                <BentoStat
                  label="ROE"
                  value={m.roe != null ? formatPercent(m.roe) : "—"}
                />
                <BentoStat
                  label="Margin"
                  value={m.profit_margin != null ? formatPercent(m.profit_margin) : "—"}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Company Stats</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <div className="grid grid-cols-2 gap-2">
                <BentoStat
                  label="Rev Growth (QoQ)"
                  value={
                    m.quarterly_revenue_growth != null
                      ? `${m.quarterly_revenue_growth.toFixed(2)}%`
                      : "—"
                  }
                />
                <BentoStat
                  label="Debt (Liabilities)"
                  value={m.liabilities ? formatCompactNumber(m.liabilities) : "—"}
                />
                <BentoStat
                  label="Assets"
                  value={m.assets ? formatCompactNumber(m.assets) : "—"}
                />
                <BentoStat
                  label="Net Balance"
                  value={m.equity ? formatCompactNumber(m.equity) : "—"}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>52W Range</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-xs text-muted">
                <span>
                  {m.fifty_two_week_low != null ? formatUsd(m.fifty_two_week_low) : "—"}
                </span>
                <span>
                  {m.fifty_two_week_high != null ? formatUsd(m.fifty_two_week_high) : "—"}
                </span>
              </div>
              {m.fifty_two_week_low != null && m.fifty_two_week_high != null ? (
                <RangeBar low={m.fifty_two_week_low} high={m.fifty_two_week_high} value={m.price} />
              ) : (
                <div className="mt-2 h-2 w-full rounded-full bg-[rgb(var(--surface-2)/0.65)]" />
              )}
            </CardContent>
          </Card>
        </div>
      </motion.div>
    </div>
  );
}

function Chart({ ticker, fullscreen }: { ticker: string; fullscreen?: boolean }) {
  const [tf, setTf] = React.useState<"1W" | "1M" | "1Y" | "MAX">("1M");
  const quote = useQuote(ticker);
  const up = (quote.data?.pct_change ?? 0) >= 0;
  const stroke = up ? "rgb(var(--emerald))" : "rgb(var(--rose))";

  const params =
    tf === "1W"
      ? { period: "7d", interval: "30m" }
      : tf === "1M"
        ? { period: "1mo", interval: "1d" }
        : tf === "1Y"
          ? { period: "1y", interval: "1d" }
          : { period: "max", interval: "1wk" };

  const history = useHistory(ticker, params);
  const chartData = (history.data ?? []).map((d) => ({ t: d.Date, v: d.Close }));

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold tracking-tight">Chart</div>
        <div className="flex items-center gap-1 rounded-xl border border-border/40 bg-[rgb(var(--surface-1)/0.45)] p-1">
          {(["1W", "1M", "1Y", "MAX"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setTf(k)}
              className={cn(
                "h-8 rounded-lg px-3 text-xs font-semibold transition-colors",
                tf === k
                  ? "bg-[rgb(var(--surface-2)/0.85)] text-foreground"
                  : "text-muted hover:text-foreground",
              )}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      <div
        className={cn(
          "rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] p-3 backdrop-blur",
          fullscreen ? "h-[460px]" : "h-[260px]",
        )}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ left: 8, right: 12, top: 8, bottom: 8 }}
          >
            <defs>
              <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="t"
              tickLine={false}
              axisLine={false}
              minTickGap={24}
              tick={{ fill: "rgb(var(--muted))", fontSize: 11 }}
              tickFormatter={(v) => formatXAxisLabel(tf, String(v))}
            />
            <YAxis
              width={56}
              tickLine={false}
              axisLine={false}
              domain={["dataMin", "dataMax"]}
              tick={{ fill: "rgb(var(--muted))", fontSize: 11 }}
              tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
            />
            <Tooltip
              cursor={{ stroke: "rgb(var(--border)/0.35)" }}
              contentStyle={{
                background: "rgb(var(--surface-1)/0.92)",
                border: "1px solid rgb(var(--border)/0.4)",
                borderRadius: 12,
              }}
              labelFormatter={(label) => formatXAxisLabel(tf, String(label))}
              formatter={(v: unknown) => [formatUsd(Number(v)), "Price"]}
            />
            <Area
              type="monotone"
              dataKey="v"
              stroke={stroke}
              fill="url(#fill)"
              fillOpacity={1}
              isAnimationActive
              animationDuration={240}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="text-xs text-muted">
        {history.isFetching ? "Refreshing…" : "Area chart."}
      </div>
    </div>
  );
}

export function DetailPanel({
  ticker,
  open,
  onOpenChange,
  fullscreen,
}: {
  ticker: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fullscreen?: boolean;
}) {
  const desktop = useMediaQuery("(min-width: 1280px)");

  const content = ticker ? (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold tracking-tight">Details</div>
        <div className="text-xs text-muted">{ticker}</div>
      </div>

      <Overview ticker={ticker} fullscreen={fullscreen} />
    </div>
  ) : (
    <div className="grid place-items-center rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] p-6 text-center text-sm text-muted backdrop-blur">
      Select a stock to view details.
    </div>
  );

  if (desktop) {
    if (fullscreen) {
      return (
        <Dialog open={open} onOpenChange={onOpenChange}>
          <DialogContent className="h-[calc(100vh-1.25rem)] w-[calc(100vw-1.25rem)] max-w-none overflow-auto p-4">
            {content}
          </DialogContent>
        </Dialog>
      );
    }

    return (
      <aside className="hidden w-[420px] shrink-0 border-l border-border/40 bg-[rgb(var(--surface-1)/0.25)] p-4 backdrop-blur-xl xl:block">
        {content}
      </aside>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(900px,calc(100vw-1.25rem))]">
        {content}
      </DialogContent>
    </Dialog>
  );
}
