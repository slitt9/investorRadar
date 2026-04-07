"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { getUsMarketStatus } from "@/lib/market-status";
import { cn } from "@/lib/cn";

export function MarketStatusPill() {
  const [status, setStatus] = React.useState(() => getUsMarketStatus());

  React.useEffect(() => {
    const id = window.setInterval(() => setStatus(getUsMarketStatus()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "relative h-2 w-2 rounded-full",
          status.isOpen ? "bg-emerald" : "bg-border",
        )}
        aria-hidden
      >
        {status.isOpen && (
          <span className="absolute inset-0 animate-ping rounded-full bg-emerald/50" />
        )}
      </div>
      <Badge variant={status.isOpen ? "emerald" : "default"} className="py-0.5">
        {status.label}
      </Badge>
      <div className="hidden text-xs text-muted xl:block">
        {status.opensAt} – {status.closesAt}
      </div>
    </div>
  );
}

