"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { FiltersPanel } from "@/features/screener/components/filters-panel";
import { ResultsTable } from "@/features/screener/components/results-table";
import { ScreenerDetailDialog } from "@/features/screener/components/detail-panel";
import { MobileFilters } from "@/features/screener/components/mobile-filters";
import {
  useScreenerFilters,
  useScreenerResults,
} from "@/features/screener/use-screener";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";

export function ScreenerView() {
  const { draft, setDraft, applied, apply, reset } = useScreenerFilters();
  const results = useScreenerResults(applied);
  const { data, isFetching, isLoading } = results;
  const rows = data ?? [];

  const searchParams = useSearchParams();
  const requestedTicker = searchParams.get("ticker")?.toUpperCase() ?? null;

  const [filtersCollapsed, setFiltersCollapsed] = React.useState(false);
  const [selectedTicker, setSelectedTicker] = React.useState<string | null>(null);

  const hasDraftChanges = React.useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(applied),
    [applied, draft],
  );

  React.useEffect(() => {
    if (!requestedTicker) return;
    setSelectedTicker(requestedTicker);
  }, [requestedTicker]);

  const loading = isLoading || isFetching;

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-0 w-full gap-3 overflow-hidden pr-1 lg:pr-2">
      <FiltersPanel
        value={draft}
        onChange={setDraft}
        onApply={apply}
        onReset={reset}
        collapsed={filtersCollapsed}
        onToggleCollapsed={() => setFiltersCollapsed((v) => !v)}
        className="hidden lg:block"
      />

      <section className="grid min-h-0 min-w-0 flex-1 grid-rows-[auto_minmax(0,1fr)] overflow-hidden p-4 lg:p-6 xl:p-8">
        <header className="mb-4 flex shrink-0 flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-muted">
                S&amp;P 500
              </span>
              <span className="h-[2px] w-10 rounded-full bg-[linear-gradient(90deg,rgb(var(--blue)/0.85),rgb(var(--purple)/0.65),transparent)]" />
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-[26px]">
              S&amp;P 500 screener
            </h1>
            <p className="mt-1 hidden max-w-[60ch] text-sm text-muted sm:block">
              All 500 constituents are filterable. Slide a control or press Enter
              in the search box to narrow the list, then open a row for the full
              breakdown.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <MobileFilters
              value={draft}
              onChange={setDraft}
              onApply={apply}
              onReset={reset}
            />
            {hasDraftChanges && (
              <>
                <Button
                  variant="subtle"
                  size="sm"
                  className="hidden md:inline-flex"
                  onClick={reset}
                >
                  Reset
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  className="hidden md:inline-flex"
                  onClick={apply}
                >
                  Apply Changes
                </Button>
              </>
            )}
            <div
              className={cn(
                "hidden items-center gap-2 rounded-full border border-border/40 bg-[rgb(var(--surface-1)/0.55)] px-3 py-1 text-xs text-muted backdrop-blur md:inline-flex",
                loading && "border-[rgb(var(--blue)/0.35)] text-foreground",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  loading
                    ? "animate-pulse bg-blue"
                    : hasDraftChanges
                      ? "bg-purple"
                      : "bg-emerald",
                )}
              />
              {loading ? "Refreshing" : hasDraftChanges ? "Draft changes" : "Ready"}
            </div>
          </div>
        </header>

        <div className="min-h-0 overflow-hidden">
          {results.isError && (
            <div className="mb-3 rounded-2xl border border-[rgb(var(--rose)/0.35)] bg-[rgb(var(--rose)/0.10)] p-4 text-sm">
              <div className="font-semibold tracking-tight">Backend unreachable</div>
              <div className="mt-1 text-xs text-muted">
                Start the Flask API on{" "}
                <span className="text-foreground">http://localhost:5000</span>{" "}
                (run <span className="text-foreground">python backend/app.py</span>) or
                set{" "}
                <span className="text-foreground">NEXT_PUBLIC_API_BASE_URL</span>{" "}
                (Vercel Services will also inject{" "}
                <span className="text-foreground">NEXT_PUBLIC_BACKEND_URL</span>{" "}
                automatically).
              </div>
              <div className="mt-2 text-xs text-muted">
                If you’re using Render Free, the service may be waking up (30–60s).
                Then hit Retry.
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
            onSelect={(row) => setSelectedTicker(row.ticker)}
          />
        </div>
      </section>

      <ScreenerDetailDialog
        ticker={selectedTicker}
        open={Boolean(selectedTicker)}
        onOpenChange={(o) => {
          if (!o) setSelectedTicker(null);
        }}
      />
    </div>
  );
}
