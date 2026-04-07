"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { FiltersPanel } from "@/features/screener/components/filters-panel";
import { ResultsTable } from "@/features/screener/components/results-table";
import { DetailPanel } from "@/features/screener/components/detail-panel";
import { MobileFilters } from "@/features/screener/components/mobile-filters";
import { useScreenerFilters, useScreenerResults } from "@/features/screener/use-screener";
import { cn } from "@/lib/cn";

export function ScreenerView() {
  const { draft, setDraft, applied, apply, reset } = useScreenerFilters();
  const results = useScreenerResults(applied);
  const { data, isFetching, isLoading } = results;
  const rows = data ?? [];

  const searchParams = useSearchParams();
  const requestedTicker = searchParams.get("ticker")?.toUpperCase() ?? null;

  const [filtersCollapsed, setFiltersCollapsed] = React.useState(false);
  const [selectedTicker, setSelectedTicker] = React.useState<string | null>(null);
  const [detailOpen, setDetailOpen] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);

  React.useEffect(() => {
    if (!requestedTicker) return;
    setSelectedTicker(requestedTicker);
    setDetailOpen(true);
  }, [requestedTicker]);

  const loading = isLoading || isFetching;

  return (
    <div className="flex min-h-0 w-full">
      <FiltersPanel
        value={draft}
        onChange={setDraft}
        onApply={apply}
        onReset={reset}
        collapsed={filtersCollapsed}
        onToggleCollapsed={() => setFiltersCollapsed((v) => !v)}
        className="hidden lg:block"
      />

      <section className="min-w-0 flex-1 p-4 lg:p-6">
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>
            <div className="text-xs text-muted">Screener</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight">
              Find opportunities, fast.
            </div>
            <div className="mt-2 max-w-[60ch] text-sm text-muted">
              Sort every column, collapse panels, and drill into bento-style fundamentals.
            </div>
          </div>
          <div className="flex items-center gap-2">
            <MobileFilters value={draft} onChange={setDraft} onApply={apply} onReset={reset} />
            <div
              className={cn(
                "hidden rounded-full border border-border/40 bg-[rgb(var(--surface-1)/0.55)] px-3 py-1 text-xs text-muted backdrop-blur md:block",
                loading && "border-[rgb(var(--blue)/0.35)]",
              )}
            >
              {loading ? "Live refresh" : "Ready"}
            </div>
          </div>
        </div>

        <div className="h-[calc(100vh-8.5rem)] min-h-[520px]">
          {results.isError && (
            <div className="mb-3 rounded-2xl border border-[rgb(var(--rose)/0.35)] bg-[rgb(var(--rose)/0.10)] p-4 text-sm">
              <div className="font-semibold tracking-tight">Backend unreachable</div>
              <div className="mt-1 text-xs text-muted">
                Start the Flask API on <span className="text-foreground">http://localhost:5000</span>{" "}
                (run <span className="text-foreground">python backend/app.py</span>) or set{" "}
                <span className="text-foreground">NEXT_PUBLIC_API_BASE_URL</span> (Vercel Services will also inject{" "}
                <span className="text-foreground">NEXT_PUBLIC_BACKEND_URL</span> automatically).
              </div>
              <div className="mt-2 text-xs text-muted">
                If you’re using Render Free, the service may be waking up (30–60s). Then hit Retry.
              </div>
              <div className="mt-3">
                <button
                  className="inline-flex h-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] px-3 text-xs font-semibold text-foreground transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                  onClick={() => results.refetch()}
                >
                  Retry
                </button>
              </div>
            </div>
          )}
          <ResultsTable
            rows={rows}
            loading={loading}
            selectedTicker={selectedTicker ?? undefined}
            onSelect={(row) => {
              setSelectedTicker(row.ticker);
              setFullscreen(false);
              setDetailOpen(true);
            }}
            onRowDoubleClick={(row) => {
              setSelectedTicker(row.ticker);
              setFullscreen(true);
              setDetailOpen(true);
            }}
          />
        </div>
      </section>

      <DetailPanel
        ticker={selectedTicker}
        open={detailOpen}
        onOpenChange={(o) => {
          setDetailOpen(o);
          if (!o) setFullscreen(false);
        }}
        fullscreen={fullscreen}
      />
    </div>
  );
}
