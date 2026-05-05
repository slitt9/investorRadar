"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { MarketStatusPill } from "@/components/shell/market-status-pill";

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/40 bg-[rgb(var(--surface-1)/0.35)] backdrop-blur-xl">
      <div className="flex h-16 items-center justify-end gap-4 px-4 lg:px-6">
        <MarketStatusPill />
        <Avatar>
          <AvatarFallback>SR</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
