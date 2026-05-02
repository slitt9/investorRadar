export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatUsd(value: number, opts?: { maximumFractionDigits?: number }) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: opts?.maximumFractionDigits ?? 2,
  }).format(value);
}

export function formatPercent(value: number, opts?: { maximumFractionDigits?: number }) {
  return `${(value * 100).toFixed(opts?.maximumFractionDigits ?? 2)}%`;
}

