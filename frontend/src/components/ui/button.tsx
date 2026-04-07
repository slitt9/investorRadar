"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--blue)/0.55)] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[rgb(var(--surface-2)/0.85)] text-foreground hover:bg-[rgb(var(--surface-2)/1)] border border-border/40",
        primary:
          "border border-[rgb(var(--blue)/0.35)] bg-[linear-gradient(135deg,rgb(var(--blue)/0.20),rgb(var(--purple)/0.18))] text-foreground hover:bg-[linear-gradient(135deg,rgb(var(--blue)/0.28),rgb(var(--purple)/0.24))]",
        ghost:
          "bg-transparent hover:bg-[rgb(var(--surface-2)/0.55)] text-foreground",
        subtle:
          "bg-[rgb(var(--surface-1)/0.55)] hover:bg-[rgb(var(--surface-1)/0.75)] border border-border/30",
        danger:
          "border border-[rgb(var(--rose)/0.35)] bg-[rgb(var(--rose)/0.12)] hover:bg-[rgb(var(--rose)/0.18)]",
      },
      size: {
        sm: "h-9 px-3",
        md: "h-10 px-4",
        lg: "h-11 px-5",
        icon: "h-10 w-10 px-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

