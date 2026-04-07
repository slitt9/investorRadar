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

function ChangeCell({ value }: { value: number }) {
  const up = value >= 0;
  return (
    <div className={cn("font-medium tabular-nums", up ? "text-emerald" : "text-rose")}>
      {up ? "+" : ""}
      {Number(value).toFixed(2)}%
    </div>
  );
}

export function ResultsTable({
  rows,
  loading,
  onSelect,
  selectedTicker,
  onRowDoubleClick,
}: {
  rows: ScreenerRow[];
  loading: boolean;
  onSelect: (row: ScreenerRow) => void;
  selectedTicker?: string;
  onRowDoubleClick?: (row: ScreenerRow) => void;
}) {
  const watchlist = useWatchlist();
  const columns = React.useMemo<ColumnDef<ScreenerRow>[]>(
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
        header: "Company Name",
        accessorKey: "company_name",
        cell: ({ getValue }) => (
          <div className="max-w-[240px] truncate text-sm">
            {getValue<string>()}
          </div>
        ),
      },
      {
        header: "Price",
        accessorKey: "price",
        cell: ({ getValue }) => (
          <div className="tabular-nums">{formatUsd(getValue<number>())}</div>
        ),
      },
      {
        header: "% Change",
        accessorKey: "pct_change",
        cell: ({ getValue }) => <ChangeCell value={getValue<number>()} />,
      },
      {
        header: "Volume",
        accessorKey: "volume",
        cell: ({ getValue }) => (
          <div className="tabular-nums">
            {formatCompactNumber(getValue<number>())}
          </div>
        ),
      },
      {
        header: "Market Cap",
        accessorKey: "market_cap",
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          return (
            <div className="tabular-nums">
              {typeof v === "number" ? formatCompactNumber(v) : "—"}
            </div>
          );
        },
      },
      {
        header: "P/E",
        accessorKey: "pe_ratio",
        cell: ({ getValue }) => {
          const v = getValue<number | null>();
          return (
            <div className="tabular-nums">
              {typeof v === "number" ? Number(v).toFixed(2) : "—"}
            </div>
          );
        },
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
    estimateSize: () => 44,
    overscan: 12,
  });

  const virtualRows = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const paddingTop = virtualRows.length > 0 ? virtualRows[0]!.start : 0;
  const paddingBottom =
    virtualRows.length > 0
      ? totalSize - virtualRows[virtualRows.length - 1]!.end
      : 0;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-border/40 bg-[rgb(var(--surface-1)/0.35)] shadow-[0_20px_60px_rgb(0_0_0/0.25)] backdrop-blur">
      <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
        <div>
          <div className="text-sm font-semibold tracking-tight">Results</div>
          <div className="text-xs text-muted">
            {loading
              ? "Refreshing…"
              : `${table.getRowModel().rows.length.toLocaleString()} matches`}
          </div>
        </div>
        <div className="text-xs text-muted">Click a row for details</div>
      </div>

      <div ref={parentRef} className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[rgb(var(--surface-1)/0.92)] backdrop-blur">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border/40">
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      colSpan={header.colSpan}
                      className={cn(
                        "px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted",
                        canSort && "cursor-pointer select-none hover:text-foreground",
                      )}
                      onClick={
                        canSort ? header.column.getToggleSortingHandler() : undefined
                      }
                      aria-sort={
                        sorted === "asc"
                          ? "ascending"
                          : sorted === "desc"
                            ? "descending"
                            : "none"
                      }
                    >
                      <div className="flex items-center gap-2">
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
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            ))}
          </thead>

          <tbody>
            {loading ? (
              Array.from({ length: 12 }).map((_, i) => (
                <tr key={i} className="border-b border-border/20">
                  {Array.from({ length: 8 }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <>
                {paddingTop > 0 && (
                  <tr>
                    <td style={{ height: paddingTop }} colSpan={8} />
                  </tr>
                )}

                {virtualRows.map((vr) => {
                  const row = table.getRowModel().rows[vr.index]!;
                  const data = row.original;
                  const isSelected = data.ticker === selectedTicker;
                  const tint = data.pct_change >= 0 ? "emerald" : "rose";
                  const watched = watchlist.has(data.ticker);

                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        "group border-b border-border/20 transition-colors",
                        isSelected
                          ? "bg-[linear-gradient(135deg,rgb(var(--blue)/0.10),rgb(var(--purple)/0.08))]"
                          : tint === "emerald"
                            ? "hover:bg-[rgb(var(--emerald)/0.06)]"
                            : "hover:bg-[rgb(var(--rose)/0.06)]",
                      )}
                      onClick={() => onSelect(data)}
                      onDoubleClick={() => onRowDoubleClick?.(data)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") onSelect(data);
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-3">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  watchlist.toggle(data.ticker);
                                }}
                                aria-label={watched ? "Remove from watchlist" : "Add to watchlist"}
                              >
                                <Star
                                  className={cn(
                                    "h-4 w-4",
                                    watched && "text-[rgb(var(--blue)/0.95)] fill-[rgb(var(--blue)/0.30)]",
                                  )}
                                />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {watched ? "Remove from watchlist" : "Add to watchlist"}
                            </TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
                                onClick={(e) => e.stopPropagation()}
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
                    <td style={{ height: paddingBottom }} colSpan={8} />
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
