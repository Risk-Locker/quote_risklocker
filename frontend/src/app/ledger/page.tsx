"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type { Route } from "next";
import {
  CalendarBlank,
  ChartLineUp,
  Database,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { InsightsAnalyticsView } from "@/components/insights/insights-analytics-view";
import { SyncSessionsModal } from "@/components/insights/sync-sessions-modal";
import { VehicleHistoryModal } from "@/components/insights/vehicle-history-modal";
import { TenureTimelineLedger } from "@/components/tenures/tenure-timeline-ledger";
import { Button } from "@/components/ui/button";

type TabKey = "timeline" | "analytics";

function LedgerContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = searchParams.get("tab");
  const initialTab: TabKey = rawTab === "analytics" ? "analytics" : "timeline";

  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [inspectPlate, setInspectPlate] = useState<string | null>(null);

  // Sync tab with URL
  function handleTabChange(tab: TabKey) {
    setActiveTab(tab);
    if (tab === "timeline") {
      router.replace("/ledger" as Route, { scroll: false });
    } else {
      router.replace(`/ledger?tab=${tab}` as Route, { scroll: false });
    }
  }

  useEffect(() => {
    const t = searchParams.get("tab");
    if (t === "analytics") {
      setActiveTab("analytics");
    } else {
      setActiveTab("timeline");
    }
  }, [searchParams]);

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-10 py-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-neutral-200/80 pb-5">
        <div>
          <h1 className="text-xl font-bold text-neutral-900 tracking-tight flex items-center gap-2">
            <span>Motor Renewal Ledger</span>
          </h1>
          <p className="text-xs text-neutral-500 mt-1">
            Monthly policy expiry anchors, customer tenures, multi-quote comparisons, and renewal tracking.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* View Switcher: Renewal Ledger vs Analytics */}
          <div className="flex items-center gap-1 bg-neutral-100 p-1 rounded-lg border border-neutral-200">
            <button
              type="button"
              onClick={() => handleTabChange("timeline")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === "timeline"
                  ? "bg-white text-neutral-950 shadow-xs"
                  : "text-neutral-500 hover:text-neutral-800"
              }`}
            >
              <CalendarBlank size={14} weight={activeTab === "timeline" ? "bold" : "regular"} />
              <span>Renewal Ledger</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabChange("analytics")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === "analytics"
                  ? "bg-white text-neutral-950 shadow-xs"
                  : "text-neutral-500 hover:text-neutral-800"
              }`}
            >
              <ChartLineUp size={14} weight={activeTab === "analytics" ? "bold" : "regular"} />
              <span>Analytics &amp; Conversion</span>
            </button>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowSyncModal(true)}
            className="text-xs h-8 border-neutral-200 text-neutral-800 hover:bg-neutral-50 gap-1.5 font-medium shadow-2xs"
            title="Inspect and sync past quotation sessions into vehicle tracking and calendar ledger"
          >
            <Database size={14} weight="bold" />
            Sync Past Sessions
          </Button>
        </div>
      </div>

      {/* Active View */}
      <div>
        {activeTab === "timeline" && <TenureTimelineLedger />}
        {activeTab === "analytics" && <InsightsAnalyticsView />}
      </div>

      {/* Two-Step Past Sessions Sync Modal */}
      <SyncSessionsModal
        isOpen={showSyncModal}
        onClose={() => setShowSyncModal(false)}
        onSyncComplete={() => {
          router.refresh();
        }}
      />

      {/* Vehicle Ownership History Modal */}
      <VehicleHistoryModal
        vehicleNo={inspectPlate}
        onClose={() => setInspectPlate(null)}
      />
    </div>
  );
}

export default function LedgerPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-12 text-center text-xs text-neutral-400">Loading ledger...</div>}>
        <LedgerContent />
      </Suspense>
    </AppShell>
  );
}
