"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import { ArrowLeft, CalendarBlank } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { ComparisonMatrix } from "@/components/comparison/comparison-matrix";
import { api } from "@/lib/api";

function ComparisonContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tenureId = searchParams.get("tenure_id");
  const initCalledRef = useRef(false);

  useEffect(() => {
    if (!tenureId && !initCalledRef.current) {
      initCalledRef.current = true;
      const today = new Date().toISOString().split("T")[0];
      const endDate = new Date(Date.now() + 364 * 86400000).toISOString().split("T")[0];
      api<{ id?: string; tenure?: { id: string } }>("/tenures", {
        method: "POST",
        body: JSON.stringify({
          customer_name: "New Quotation Intake",
          vehicle_no: "UNPLATED",
          coverage_start_date: today,
          coverage_end_date: endDate,
        }),
      })
        .then((res) => {
          const targetId = res?.id || res?.tenure?.id;
          if (targetId) {
            router.replace(`/comparison?tenure_id=${targetId}` as Route);
          } else {
            router.replace("/upload/marketing-comparison" as Route);
          }
        })
        .catch(() => {
          router.replace("/upload/marketing-comparison" as Route);
        });
    }
  }, [tenureId, router]);

  if (!tenureId) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="size-7 animate-spin rounded-full border-2 border-neutral-900 border-t-transparent" />
        <p className="text-xs text-neutral-500 font-medium">Initializing Marketing Comparison Workspace...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Ledger Breadcrumb Navigation */}
      <div className="flex items-center justify-between no-print print:hidden">
        <Link
          href={"/upload/marketing-comparison" as Route}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-neutral-600 hover:text-neutral-950 bg-neutral-100 hover:bg-neutral-200/80 transition-colors"
        >
          <ArrowLeft size={14} weight="bold" />
          <span>Back to Quotation Intake</span>
        </Link>

        <div className="flex items-center gap-2 text-xs text-neutral-500 font-medium">
          <CalendarBlank size={14} className="text-neutral-400" />
          <span>Vehicle Policy Tenure Comparison</span>
        </div>
      </div>

      {/* Side-by-Side Comparison Matrix for this Tenure */}
      <ComparisonMatrix tenureId={tenureId} />
    </div>
  );
}

export default function ComparisonPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <div className="size-8 animate-spin rounded-full border-2 border-neutral-900 border-t-transparent" />
          </div>
        }
      >
        <ComparisonContent />
      </Suspense>
    </AppShell>
  );
}
