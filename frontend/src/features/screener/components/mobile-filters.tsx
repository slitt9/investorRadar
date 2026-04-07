"use client";

import * as React from "react";
import { SlidersHorizontal } from "lucide-react";
import type { ScreenerFilters } from "../types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCompactNumber, formatUsd } from "@/lib/format";

function RangeLabel({ left, right }: { left: string; right: string }) {
  return (
    <div className="mt-2 flex items-center justify-between text-xs text-muted">
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}

export function MobileFilters({
  value,
  onChange,
  onApply,
  onReset,
}: {
  value: ScreenerFilters;
  onChange: (next: ScreenerFilters) => void;
  onApply: () => void;
  onReset: () => void;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <>
      <Button
        variant="subtle"
        onClick={() => setOpen(true)}
        className="lg:hidden"
      >
        <SlidersHorizontal className="h-4 w-4" />
        Filters
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="p-0">
          <div className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="text-sm font-semibold tracking-tight">Filters</div>
              <div className="text-xs text-muted">Apply to refresh results</div>
            </div>
          </div>
          <Separator />
          <div className="max-h-[70vh] overflow-auto p-4">
            <div className="grid gap-5">
              <div>
                <div className="text-xs font-semibold tracking-wide text-muted">
                  Sector
                </div>
                <div className="mt-2">
                  <Select
                    value={value.sector}
                    onValueChange={(sector) =>
                      onChange({
                        ...value,
                        sector: sector as ScreenerFilters["sector"],
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All sectors" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="All">All</SelectItem>
                      <SelectItem value="Technology">Technology</SelectItem>
                      <SelectItem value="Financials">Financials</SelectItem>
                      <SelectItem value="Healthcare">Healthcare</SelectItem>
                      <SelectItem value="Energy">Energy</SelectItem>
                      <SelectItem value="Consumer">Consumer</SelectItem>
                      <SelectItem value="Industrials">Industrials</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-muted">
                    Market Cap
                  </div>
                  <div className="text-xs text-muted">
                    {formatCompactNumber(value.marketCap[0])} –{" "}
                    {formatCompactNumber(value.marketCap[1])}
                  </div>
                </div>
                <div className="mt-3">
                  <Slider
                    value={value.marketCap}
                    min={0}
                    max={2_000_000_000_000}
                    step={50_000_000}
                    onValueChange={(marketCap) =>
                      onChange({
                        ...value,
                        marketCap: marketCap as [number, number],
                      })
                    }
                  />
                  <RangeLabel left="0" right="2T" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-muted">
                    P/E Ratio
                  </div>
                  <div className="text-xs text-muted">
                    {value.pe[0].toFixed(0)} – {value.pe[1].toFixed(0)}
                  </div>
                </div>
                <div className="mt-3">
                  <Slider
                    value={value.pe}
                    min={0}
                    max={80}
                    step={1}
                    onValueChange={(pe) =>
                      onChange({ ...value, pe: pe as [number, number] })
                    }
                  />
                  <RangeLabel left="0" right="80+" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-muted">
                    Volume
                  </div>
                  <div className="text-xs text-muted">
                    {formatCompactNumber(value.volume[0])} –{" "}
                    {formatCompactNumber(value.volume[1])}
                  </div>
                </div>
                <div className="mt-3">
                  <Slider
                    value={value.volume}
                    min={0}
                    max={100_000_000}
                    step={250_000}
                    onValueChange={(volume) =>
                      onChange({
                        ...value,
                        volume: volume as [number, number],
                      })
                    }
                  />
                  <RangeLabel left="0" right="100M" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold tracking-wide text-muted">
                    Price
                  </div>
                  <div className="text-xs text-muted">
                    {formatUsd(value.price[0], { maximumFractionDigits: 0 })} –{" "}
                    {formatUsd(value.price[1], { maximumFractionDigits: 0 })}
                  </div>
                </div>
                <div className="mt-3">
                  <Slider
                    value={value.price}
                    min={0}
                    max={600}
                    step={1}
                    onValueChange={(price) =>
                      onChange({ ...value, price: price as [number, number] })
                    }
                  />
                  <RangeLabel left="$0" right="$600" />
                </div>
              </div>

            </div>
          </div>
          <Separator />
          <div className="p-4">
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="subtle"
                onClick={() => {
                  onReset();
                  setOpen(false);
                }}
              >
                Reset
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  onApply();
                  setOpen(false);
                }}
              >
                Apply
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
