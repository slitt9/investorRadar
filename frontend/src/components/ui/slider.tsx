"use client";

import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/cn";

export const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
    thumbCount?: number;
  }
>(({ className, thumbCount, value, defaultValue, ...props }, ref) => {
  const inferredCount =
    thumbCount ??
    (Array.isArray(value)
      ? value.length
      : Array.isArray(defaultValue)
        ? defaultValue.length
        : 1);

  const count = Math.max(1, inferredCount);

  return (
    <SliderPrimitive.Root
      ref={ref}
      value={value}
      defaultValue={defaultValue}
      className={cn(
        "relative flex w-full touch-none select-none items-center",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-[rgb(var(--surface-2)/0.75)]">
        <SliderPrimitive.Range className="absolute h-full bg-[rgb(var(--blue)/0.75)]" />
      </SliderPrimitive.Track>
      {Array.from({ length: count }).map((_, i) => (
        <SliderPrimitive.Thumb
          // Radix expects a Thumb per value.
          key={i}
          className="block h-5 w-5 rounded-full border border-border/40 bg-[rgb(var(--surface-1)/0.95)] shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.25)]"
        />
      ))}
    </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;
