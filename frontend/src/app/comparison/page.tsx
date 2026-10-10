"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import { ArrowLeft, CalendarBlank } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { ComparisonMatrix } from "@/components/comparison/comparison-matrix";
import { GuidedTour } from "@/components/guided-tour";
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
      {/* Top Workspace Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 no-print print:hidden">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            href={"/upload/marketing-comparison" as Route}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-neutral-600 hover:text-neutral-950 bg-neutral-100 hover:bg-neutral-200/80 transition-colors shrink-0"
          >
            <ArrowLeft size={14} weight="bold" />
            <span>Back to Intake</span>
          </Link>
          <div className="h-4 w-px bg-neutral-200 hidden sm:block" />
          <div>
            <h1 className="text-base font-bold text-neutral-900 tracking-tight">
              Marketing Comparison Workspace
            </h1>
            <p className="text-[11px] text-neutral-500 font-medium">
              Side-by-side market benchmarking, version revisions, and policy issuance
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <GuidedTour
            storageKey="tour:marketing-comparison"
            launcherLabel="Workspace Guide"
            title="Marketing Comparison Workspace Guide"
            description="Learn how to compare underwriter quotes, manage versions, and issue policies in 5 simple steps."
            steps={[
              {
                target: "#tour-stepper",
                title: "1. 3-Stage Workflow",
                body: "Follow the 3-stage flow: Compare Underwriters → Pick Recommended Winner → Issue Client Quotation.",
                position: "bottom",
              },
              {
                target: "#tour-comparison-matrix",
                title: "2. Underwriter Columns",
                body: "Quotes are aligned side-by-side. Use the inline version tabs (v1, v2, v3) on any column to switch revisions.",
                position: "top",
              },
              {
                target: "#tour-customer-ledger",
                title: "3. Customer & Vehicle Ledger",
                body: "Review vehicle specs, NCD%, and road tax + runner fee. Click the pencil icon to update customer or car details.",
                position: "left",
              },
              {
                target: "#tour-current-policy",
                title: "4. Current Policy & Recoveries",
                body: "View the official policy PDF. If unlinked, expand 'Previously Removed Policies' to view or re-link at any time.",
                position: "left",
              },
            ]}
          />
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
