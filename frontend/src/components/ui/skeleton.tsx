import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl bg-[rgb(var(--surface-2)/0.65)]",
        "before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_1.2s_infinite] before:bg-[linear-gradient(90deg,transparent,rgb(var(--fg)/0.06),transparent)]",
        className,
      )}
    />
  );
}

