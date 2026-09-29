"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Buildings,
  CalendarBlank,
  ChartLineUp,
  Database,
  ListBullets,
  Users,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { TeamsCalendarView } from "@/components/insights/teams-calendar-view";
import { HitMissCalendar } from "@/components/insights/hit-miss-calendar";
import { ConnectedClientDossier } from "@/components/insights/connected-client-dossier";
import { InsightsAnalyticsView } from "@/components/insights/insights-analytics-view";
import { SyncSessionsModal } from "@/components/insights/sync-sessions-modal";
import { VehicleHistoryModal } from "@/components/insights/vehicle-history-modal";
import { TenureTimelineLedger } from "@/components/tenures/tenure-timeline-ledger";
import { Button } from "@/components/ui/button";

type TabKey = "timeline" | "clients" | "hit-miss" | "corporate" | "analytics" | "calendar";

function InsightsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialTab = (searchParams.get("tab") as TabKey) || "timeline";

  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [inspectPlate, setInspectPlate] = useState<string | null>(null);

  // Sync tab with URL
  function handleTabChange(tab: TabKey) {
    setActiveTab(tab);
    router.replace(`/insights?tab=${tab}`, { scroll: false });
  }

  useEffect(() => {
    const t = searchParams.get("tab") as TabKey;
    if (t && ["timeline", "clients", "hit-miss", "corporate", "analytics", "calendar"].includes(t)) {
      setActiveTab(t);
    }
  }, [searchParams]);

  return (
    <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-10 py-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-neutral-200/80 pb-5">
        <div>
          <h1 className="text-xl font-bold text-neutral-900 tracking-tight flex items-center gap-2">
            <span>Tenures &amp; Timeline Ledger</span>
          </h1>
          <p className="text-xs text-neutral-500 mt-1">
            Monthly policy expiry anchors, customer tenures, multi-quote comparisons, and conversion outcomes.
          </p>
        </div>

        <div className="flex items-center gap-2">
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

      {/* 6-Tab Navigation Switcher */}
      <div className="flex items-center gap-1 bg-neutral-100/90 p-1 rounded-lg border border-neutral-200/70 w-fit overflow-x-auto max-w-full">
        {/* 1. Timeline Ledger */}
        <button
          type="button"
          onClick={() => handleTabChange("timeline")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "timeline"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <CalendarBlank size={15} weight={activeTab === "timeline" ? "bold" : "regular"} />
          <span>Timeline Ledger</span>
        </button>

        {/* 2. Client Records */}
        <button
          type="button"
          onClick={() => handleTabChange("clients")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "clients"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <Users size={15} weight={activeTab === "clients" ? "bold" : "regular"} />
          <span>Client Records</span>
        </button>

        {/* 3. Hit & Miss Activity */}
        <button
          type="button"
          onClick={() => handleTabChange("hit-miss")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "hit-miss"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <ListBullets size={15} weight={activeTab === "hit-miss" ? "bold" : "regular"} />
          <span>Hit &amp; Miss Activity</span>
        </button>

        {/* 4. Corporate Fleet */}
        <button
          type="button"
          onClick={() => handleTabChange("corporate")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "corporate"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <Buildings size={15} weight={activeTab === "corporate" ? "bold" : "regular"} />
          <span>Corporate Fleet</span>
        </button>

        {/* 5. Analytics & Conversion */}
        <button
          type="button"
          onClick={() => handleTabChange("analytics")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "analytics"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <ChartLineUp size={15} weight={activeTab === "analytics" ? "bold" : "regular"} />
          <span>Analytics &amp; Conversion</span>
        </button>

        {/* 6. Calendar */}
        <button
          type="button"
          onClick={() => handleTabChange("calendar")}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${
            activeTab === "calendar"
              ? "bg-white text-neutral-950 shadow-xs"
              : "text-neutral-500 hover:text-neutral-800"
          }`}
        >
          <CalendarBlank size={15} weight={activeTab === "calendar" ? "bold" : "regular"} />
          <span>Calendar</span>
        </button>
      </div>

      {/* Active Tab View */}
      <div>
        {activeTab === "timeline" && <TenureTimelineLedger />}

        {activeTab === "clients" && (
          <ConnectedClientDossier fixedClientType="Individual" onOpenVehicleHistory={(plate) => setInspectPlate(plate)} />
        )}

        {activeTab === "hit-miss" && <HitMissCalendar />}

        {activeTab === "corporate" && (
          <ConnectedClientDossier fixedClientType="Company" onOpenVehicleHistory={(plate) => setInspectPlate(plate)} />
        )}

        {activeTab === "analytics" && <InsightsAnalyticsView />}

        {activeTab === "calendar" && (
          <TeamsCalendarView onOpenVehicleHistory={(plate) => setInspectPlate(plate)} />
        )}
      </div>


      {/* Two-Step Past Sessions Sync Modal */}
      <SyncSessionsModal
        isOpen={showSyncModal}
        onClose={() => setShowSyncModal(false)}
        onSyncComplete={() => {
          // Re-trigger refresh if needed
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

export default function InsightsPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-12 text-center text-xs text-neutral-400">Loading insights...</div>}>
        <InsightsContent />
      </Suspense>
    </AppShell>
  );
}
