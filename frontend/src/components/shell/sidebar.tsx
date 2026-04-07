"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeft, Radar } from "lucide-react";
import { NAV_ITEMS } from "./nav-items";
import { cn } from "@/lib/cn";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <aside
      className={cn(
        "relative hidden h-[calc(100vh-1px)] shrink-0 border-r border-border/40 bg-[rgb(var(--surface-1)/0.40)] backdrop-blur-xl lg:flex",
        collapsed ? "w-[72px]" : "w-[260px]",
      )}
    >
      <div className="flex h-full w-full flex-col">
        <div className="flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl border border-border/40 bg-[linear-gradient(135deg,rgb(var(--blue)/0.18),rgb(var(--purple)/0.15))]">
              <Radar className="h-4.5 w-4.5" />
            </div>
            {!collapsed && (
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight">
                  InvestorRadar
                </div>
                <div className="text-xs text-muted">Executive</div>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] text-muted transition-colors hover:bg-[rgb(var(--surface-2)/0.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>

        <ScrollArea className="flex-1 px-2 pb-4">
          <nav className="grid gap-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;

              const link = (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-2xl px-3 py-2 text-sm transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]",
                    active
                      ? "bg-[rgb(var(--surface-2)/0.65)] text-foreground"
                      : "text-muted hover:bg-[rgb(var(--surface-2)/0.45)] hover:text-foreground",
                  )}
                >
                  {active && (
                    <span
                      aria-hidden
                      className={cn(
                        "absolute left-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-r-full",
                        item.isPrimary
                          ? "bg-[linear-gradient(180deg,rgb(var(--blue)),rgb(var(--purple)))] shadow-[0_0_16px_rgb(var(--blue)/0.45)]"
                          : "bg-[rgb(var(--blue)/0.65)]",
                      )}
                    />
                  )}
                  <div
                    className={cn(
                      "grid h-9 w-9 place-items-center rounded-xl border border-border/30 bg-[rgb(var(--surface-2)/0.35)] transition-colors group-hover:bg-[rgb(var(--surface-2)/0.55)]",
                      active && "bg-[rgb(var(--surface-2)/0.70)]",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  {!collapsed && (
                    <div className="flex items-center gap-2">
                      <span className={cn(item.isPrimary && "font-semibold")}>
                        {item.label}
                      </span>
                      {item.isPrimary && (
                        <span className="rounded-full border border-[rgb(var(--blue)/0.35)] bg-[rgb(var(--blue)/0.10)] px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                          Primary
                        </span>
                      )}
                    </div>
                  )}
                </Link>
              );

              if (!collapsed) return link;

              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              );
            })}
          </nav>
        </ScrollArea>

        <div className={cn("px-4 pb-4", collapsed && "px-2")}>
          <div className="rounded-2xl border border-border/30 bg-[rgb(var(--surface-2)/0.25)] p-3 text-xs text-muted">
            {!collapsed ? (
              <div className="leading-relaxed">
                Tip: Press <span className="text-foreground">⌘ K</span> for
                command palette.
              </div>
            ) : (
              <div className="grid place-items-center">⌘K</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

