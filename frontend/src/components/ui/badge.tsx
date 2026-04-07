import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium tracking-tight",
  {
    variants: {
      variant: {
        default: "border-border/40 bg-[rgb(var(--surface-1)/0.55)]",
        emerald: "border-[rgb(var(--emerald)/0.35)] bg-[rgb(var(--emerald)/0.12)]",
        rose: "border-[rgb(var(--rose)/0.35)] bg-[rgb(var(--rose)/0.12)]",
        info: "border-[rgb(var(--blue)/0.35)] bg-[rgb(var(--blue)/0.12)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

