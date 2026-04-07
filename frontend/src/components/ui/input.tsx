import * as React from "react";
import { cn } from "@/lib/cn";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "flex h-10 w-full rounded-xl border border-border/40 bg-[rgb(var(--surface-2)/0.55)] px-3 py-2 text-sm text-foreground placeholder:text-muted/80 shadow-sm outline-none transition-colors focus-visible:border-[rgb(var(--blue)/0.55)] focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.20)] disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

