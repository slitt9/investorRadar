import { ScreenerView } from "@/features/screener/screener-view";
import { Suspense } from "react";

export default function ScreenerPage() {
  return (
    <Suspense
      fallback={<div className="p-6 text-sm text-muted">Loading screener…</div>}
    >
      <ScreenerView />
    </Suspense>
  );
}
