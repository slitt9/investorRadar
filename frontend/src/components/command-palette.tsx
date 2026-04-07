"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { ArrowRight, Hash, Search } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { NAV_ITEMS } from "@/components/shell/nav-items";
import { cn } from "@/lib/cn";
import { useSearch } from "@/features/screener/api";

type CommandPaletteProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const [value, setValue] = React.useState("");
  const search = useSearch(value);

  React.useEffect(() => {
    if (!open) setValue("");
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0">
        <Command
          value={value}
          onValueChange={setValue}
          className="overflow-hidden rounded-2xl"
        >
          <div className="flex items-center gap-3 border-b border-border/40 bg-[rgb(var(--surface-1)/0.35)] px-4 py-3">
            <Search className="h-4 w-4 text-muted" />
            <Command.Input
              autoFocus
              placeholder="Search tickers, companies, or actions…"
              className="h-8 w-full bg-transparent text-sm text-foreground placeholder:text-muted/80 outline-none"
            />
            <div className="rounded-full border border-border/40 bg-[rgb(var(--surface-2)/0.35)] px-2 py-1 text-[10px] text-muted">
              Esc
            </div>
          </div>

          <Command.List className="max-h-[420px] overflow-auto p-2">
            <Command.Empty className="px-3 py-8 text-center text-sm text-muted">
              {value.trim().length ? "No results." : "Type to search."}
            </Command.Empty>

            <Command.Group
              heading="Navigate"
              className="px-1 py-2 text-xs text-muted"
            >
              {NAV_ITEMS.map((item) => (
                <Command.Item
                  key={item.href}
                  value={`nav:${item.label}`}
                  onSelect={() => {
                    router.push(item.href);
                    onOpenChange(false);
                  }}
                  className={cn(
                    "flex cursor-default items-center justify-between rounded-xl px-3 py-2 text-sm",
                    "aria-selected:bg-[rgb(var(--surface-2)/0.65)] aria-selected:text-foreground",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <item.icon className="h-4 w-4 text-muted" />
                    {item.label}
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted" />
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Separator className="my-2 h-px bg-border/40" />

            <Command.Group
              heading="Search"
              className="px-1 py-2 text-xs text-muted"
            >
              {(search.data ?? []).slice(0, 10).map((r) => (
                <Command.Item
                  key={r.ticker}
                  value={`ticker:${r.ticker}:${r.name}`}
                  onSelect={() => {
                    router.push(`/screener?ticker=${encodeURIComponent(r.ticker)}`);
                    onOpenChange(false);
                  }}
                  className={cn(
                    "flex cursor-default items-center justify-between rounded-xl px-3 py-2 text-sm",
                    "aria-selected:bg-[rgb(var(--surface-2)/0.65)] aria-selected:text-foreground",
                  )}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Hash className="h-4 w-4 text-muted" />
                    <span className="font-semibold tracking-tight">{r.ticker}</span>
                    <span className="truncate text-muted">{r.name}</span>
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted" />
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
