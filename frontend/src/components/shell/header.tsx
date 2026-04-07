"use client";

import * as React from "react";
import { Command, Search } from "lucide-react";
import { CommandPalette } from "@/components/command-palette";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { MarketStatusPill } from "@/components/shell/market-status-pill";

export function Header() {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border/40 bg-[rgb(var(--surface-1)/0.35)] backdrop-blur-xl">
        <div className="flex h-16 items-center justify-between gap-3 px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="subtle"
              className="hidden h-10 justify-start gap-3 px-3 text-muted lg:flex"
              onClick={() => setOpen(true)}
              aria-label="Open command palette"
            >
              <Search className="h-4 w-4" />
              <span className="text-sm">Command Palette</span>
              <span className="ml-2 inline-flex items-center gap-1 rounded-lg border border-border/30 bg-[rgb(var(--surface-2)/0.35)] px-2 py-1 text-[10px]">
                <Command className="h-3 w-3" /> K
              </span>
            </Button>
            <Button
              variant="subtle"
              size="icon"
              className="lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open command palette"
            >
              <Search className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex items-center gap-4">
            <MarketStatusPill />
            <Avatar>
              <AvatarFallback>SR</AvatarFallback>
            </Avatar>
          </div>
        </div>
      </header>

      <CommandPalette open={open} onOpenChange={setOpen} />
    </>
  );
}

