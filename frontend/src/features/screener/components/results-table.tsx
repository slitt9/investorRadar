"use client";

import * as React from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink, Star } from "lucide-react";
import type { ScreenerRow } from "../types";
import { cn } from "@/lib/cn";
import { formatCompactNumber, formatUsd } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useWatchlist } from "@/features/watchlist/watchlist-context";

/* eslint-disable react-hooks/incompatible-library */

const MISSING = (
  <span
    className="inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-[rgb(var(--muted)/0.55)]"
    aria-label="No data"
    title="No data"
  />
);

function ChangeCell({ value }: { value: number }) {
  const up = value >= 0;
  return (
    <div
      className={cn(
        "inline-flex items-center justify-end rounded-md px-2 py-0.5 text-right font-medium tabular-nums",
        up
          ? "bg-[rgb(var(--emerald)/0.10)] text-emerald"
          : "bg-[rgb(var(--rose)/0.10)] text-rose",
      )}
    >
      {up ? "+" : ""}
      {Number(value).toFixed(2)}%
    </div>
  );
}

type ColMeta = {
  headerClass?: string;
  cellClass?: string;
  align?: "left" | "right";
};

export function ResultsTable({
  rows,
  loading,
  onSelect,
  selectedTicker,
}: {
  rows: ScreenerRow[];
  loading: boolean;
  onSelect: (row: ScreenerRow) => void;
  selectedTicker?: string;
}) {
  const watchlist = useWatchlist();

  const columns = React.useMemo<ColumnDef<ScreenerRow, unknown>[]>(
    () => [
      {
        header: "Ticker",
        accessorKey: "ticker",
        cell: ({ getValue }) => (
          <div className="font-semibold tracking-tight">
            {getValue<string>()}
          </div>
        ),
      },
      {
        header: "Company",
        accessorKey: "company_name",
        cell: ({ getValue }) => (
          <div className="max-w-[min(30vw,260px)] truncate text-sm text-foreground/85">
            {getValue<string>()}
          </div>
        ),
      },
      {
        header: "Price",
        accessorKey: "price",
        meta: { align: "right" } satisfies ColMeta,
        cell: ({ getValue }) => (
          <div className="text-right tabular-nums">
            {formatUsd(getValue<number>())}
          </div>
        ),
      },
      {
        header: "% Change",
        accessorKey: "pct_change",
        meta: { align: "right" } satisfies ColMeta,
        cell: ({ getValue }) => (
          <div className="flex justify-end">
            <ChangeCell value={getValue<number>()} />
          </div>
        ),
      },
      {
        header: "Market Cap",
        accessorKey: "market_cap",
        meta: { align: "right" } satisfies ColMeta,
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          const ok = typeof v === "number" && Number.isFinite(v);
          return (
            <div className="text-right tabular-nums">
              {ok ? formatCompactNumber(v as number) : MISSING}
            </div>
          );
        },
      },
      {
        header: "P/E",
        accessorKey: "pe_ratio",
        meta: { align: "right" } satisfies ColMeta,
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          const ok = typeof v === "number" && Number.isFinite(v);
          return (
            <div className="text-right tabular-nums">
              {ok ? Number(v).toFixed(2) : MISSING}
            </div>
          );
        },
      },
      {
        header: "Sector",
        accessorKey: "sector",
        cell: ({ getValue }) => {
          const raw = getValue<string | null | undefined>();
          const s =
            raw == null || raw === "" || raw === "N/A" ? null : raw;
          return (
            <div className="max-w-[min(22vw,150px)] truncate text-xs text-muted">
              {s ?? MISSING}
            </div>
          );
        },
      },
      {
        header: "Volume",
        accessorKey: "volume",
        meta: {
          align: "right",
          headerClass: "hidden xl:table-cell",
          cellClass: "hidden xl:table-cell",
        } satisfies ColMeta,
        cell: ({ getValue }) => (
          <div className="text-right tabular-nums">
            {formatCompactNumber(getValue<number>())}
          </div>
        ),
      },
    ],
    [],
  );

  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "pct_change", desc: true },
  ]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableSortingRemoval: true,
  });

  const parentRef = React.useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: table.getRowModel().rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 12,
  });

  const virtualRows = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const paddingTop = virtualRows.length > 0 ? virtualRows[0]!.start : 0;
  const paddingBottom =
    virtualRows.length > 0
      ? totalSize - virtualRows[virtualRows.length - 1]!.end
      : 0;

  const totalColumns = columns.length + 1; // + actions

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.40)] shadow-[0_24px_80px_rgb(0_0_0/0.30)] backdrop-blur">
      <div className="flex items-center justify-between border-b border-border/40 px-5 py-3.5">
        <div>
          <div className="text-sm font-semibold tracking-tight">Results</div>
          <div className="text-xs text-muted">
            {loading
              ? "Refreshing…"
              : `${table.getRowModel().rows.length.toLocaleString()} matches`}
          </div>
        </div>
        <div className="hidden text-xs text-muted sm:block">
          Click a row to open details
        </div>
      </div>

      <div ref={parentRef} className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[rgb(var(--surface-1)/0.92)] backdrop-blur">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border/30">
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  const meta = header.column.columnDef.meta as
                    | ColMeta
                    | undefined;
                  const align = meta?.align ?? "left";
                  return (
                    <th
                      key={header.id}
                      colSpan={header.colSpan}
                      className={cn(
                        "px-5 py-3 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-muted",
                        canSort &&
                          "cursor-pointer select-none transition-colors hover:text-foreground",
                        meta?.headerClass,
                      )}
                      onClick={
                        canSort
                          ? header.column.getToggleSortingHandler()
                          : undefined
                      }
                      aria-sort={
                        sorted === "asc"
                          ? "ascending"
                          : sorted === "desc"
                            ? "descending"
                            : "none"
                      }
                    >
                      <div
                        className={cn(
                          "flex items-center gap-2",
                          align === "right" && "justify-end",
                        )}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {sorted && (
                          <span className="text-[10px] text-muted">
                            {sorted === "asc" ? "↑" : "↓"}
                          </span>
                        )}
                      </div>
                    </th>
                  );
                })}
                <th className="px-5 py-3 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-muted">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            ))}
          </thead>

          <tbody>
            {loading ? (
              Array.from({ length: 12 }).map((_, i) => (
                <tr key={i} className="border-b border-border/20">
                  {Array.from({ length: totalColumns }).map((__, j) => (
                    <td key={j} className="px-5 py-3.5">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <>
                {paddingTop > 0 && (
                  <tr>
                    <td style={{ height: paddingTop }} colSpan={totalColumns} />
                  </tr>
                )}

                {virtualRows.map((vr) => {
                  const row = table.getRowModel().rows[vr.index]!;
                  const data = row.original;
                  const isSelected = data.ticker === selectedTicker;
                  const watched = watchlist.has(data.ticker);

                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        "group relative cursor-pointer border-b border-border/15 transition-colors",
                        isSelected
                          ? "bg-[linear-gradient(135deg,rgb(var(--blue)/0.10),rgb(var(--purple)/0.08))]"
                          : "hover:bg-[rgb(var(--surface-2)/0.18)]",
                      )}
                      onClick={() => onSelect(data)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(data);
                        }
                      }}
                    >
                      {row.getVisibleCells().map((cell, idx) => {
                        const meta = cell.column.columnDef.meta as
                          | ColMeta
                          | undefined;
                        return (
                          <td
                            key={cell.id}
                            className={cn(
                              "relative px-5 py-3.5 align-middle",
                              meta?.cellClass,
                            )}
                          >
                            {idx === 0 && isSelected ? (
                              <span
                                aria-hidden
                                className="absolute inset-y-1 left-0 w-[3px] rounded-r-full bg-[linear-gradient(180deg,rgb(var(--blue)/0.95),rgb(var(--purple)/0.85))]"
                              />
                            ) : null}
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </td>
                        );
                      })}
                      <td className="px-5 py-3.5">
                        <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  watchlist.toggle(data.ticker);
                                }}
                                aria-label={
                                  watched
                                    ? "Remove from watchlist"
                                    : "Add to watchlist"
                                }
                              >
                                <Star
                                  className={cn(
                                    "h-4 w-4",
                                    watched &&
                                      "text-[rgb(var(--blue)/0.95)] fill-[rgb(var(--blue)/0.30)]",
                                  )}
                                />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {watched
                                ? "Remove from watchlist"
                                : "Add to watchlist"}
                            </TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onSelect(data);
                                }}
                                aria-label="Open details"
                              >
                                <ExternalLink className="h-4 w-4" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>Open details</TooltipContent>
                          </Tooltip>
                        </div>
                      </td>
                    </tr>
                  );
                })}

                {paddingBottom > 0 && (
                  <tr>
                    <td
                      style={{ height: paddingBottom }}
                      colSpan={totalColumns}
                    />
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
