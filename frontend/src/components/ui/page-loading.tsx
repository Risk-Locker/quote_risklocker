"use client";

import { Spinner } from "@/components/ui/spinner";

export function PageLoading() {
  return (
    <div className="grid place-items-center gap-2 py-20 text-sm text-[var(--rl-text-muted)]">
      <Spinner size={24} />
      Loading...
    </div>
  );
}
