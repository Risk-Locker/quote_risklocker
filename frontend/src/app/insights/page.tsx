"use client";

import { useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

function RedirectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab) {
      router.replace(`/ledger?tab=${tab}` as Route);
    } else {
      router.replace("/ledger" as Route);
    }
  }, [router, searchParams]);

  return (
    <div className="flex h-96 items-center justify-center">
      <p className="text-xs text-neutral-400 font-medium">Redirecting to Motor Renewal Ledger...</p>
    </div>
  );
}

export default function InsightsPage() {
  return (
    <Suspense fallback={<div className="flex h-96 items-center justify-center text-xs text-neutral-400">Loading...</div>}>
      <RedirectContent />
    </Suspense>
  );
}

